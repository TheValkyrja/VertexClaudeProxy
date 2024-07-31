import json
import os
import sys
import random
from typing import Optional, Dict, Any

import httpx
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from google.oauth2 import service_account
import google.auth.transport.requests
from secrets import compare_digest

from dotenv import load_dotenv

# 初始化 FastAPI 应用程序
app = FastAPI()

# 获取环境变量 DOCKER_ENV，如果没有设置，默认为 False
is_docker = os.environ.get('DOCKER_ENV', 'False').lower() == 'true'

#加载文件目录
def get_base_path():
    if getattr(sys, 'frozen', False):
        # 如果是打包后的可执行文件
        return os.path.dirname(sys.executable)
    else:
        # 如果是从Python运行
        return os.path.dirname(os.path.abspath(__file__))

# 加载环境变量
env_path = os.path.join(get_base_path(), '.env')
load_dotenv(env_path)

hostaddr = '0.0.0.0' if is_docker else os.getenv('HOST', '127.0.0.1')
lsnport = int(os.getenv('PORT', 5000))
project_ids = os.getenv('PROJECT_ID').split(', ')
region = os.getenv('REGION')
password = os.getenv('PASSWORD')
debug_mode = os.getenv('DEBUG', 'False').lower() == 'true'

#负载均衡加权算法
class WeightedRandomSelector:
    def __init__(self, project_ids):
        self.projects = {pid: 1 for pid in project_ids}

    def get_project(self):
        if len(self.projects) <= 1:
            return next(iter(self.projects))

        total_weight = sum(self.projects.values())
        r = random.uniform(0, total_weight)
        for pid, weight in self.projects.items():
            r -= weight
            if r <= 0:
                self._update_weights(pid)
                return pid
        return list(self.projects.keys())[-1]

    def _update_weights(self, selected_pid):
        decrease = min(self.projects[selected_pid], 0.5)
        increase = decrease / (len(self.projects) - 1)
        
        for pid in self.projects:
            if pid == selected_pid:
                self.projects[pid] -= decrease
            else:
                self.projects[pid] += increase
        
    def print_weights(self):
        print("Current project weights:")
        for pid, weight in self.projects.items():
            print(f"  {pid}: {weight:.4f}")
        print()  # 添加一个空行，使输出更易读    

# 创建一个全局的 WeightedRandomSelector 实例
global_selector = WeightedRandomSelector(project_ids)

def load_balance_selector():
    default_auth_file = os.path.join(os.path.join(get_base_path(), 'auth'), 'auth.json')
    # 检查是否存在 auth.json
    if os.path.exists(default_auth_file):
        # 如果存在 auth.json，返回第一个 project_id 和 auth.json
        return project_ids[0], default_auth_file
    else:
        # 如果不存在 auth.json，加权随机选择
        project_id = global_selector.get_project()
        auth_file = os.path.join(get_base_path(), 'auth', f'{project_id}.json')
        if not os.path.exists(auth_file):
            # 如果文件不存在，抛出 HTTPException
            raise HTTPException(
                status_code=500,
                detail="No valid authentication file found. Please check your configuration."
            )
        return project_id, auth_file

#根据验证文件取得token
def get_gcloud_token(auth_file):
    credentials = service_account.Credentials.from_service_account_file(
        auth_file, 
        scopes=['https://www.googleapis.com/auth/cloud-platform']
    )
    
    if not credentials.valid or credentials.expired:
        request = google.auth.transport.requests.Request()
        credentials.refresh(request)

    return credentials.token

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def vertex_model(original_model):
    # 定义模型名称映射
    mapping_file = os.path.join(get_base_path(), 'model_mapping.json')
    with open(mapping_file, 'r') as f:
        model_mapping = json.load(f)    
    return model_mapping[original_model]

# 比较密码
def check_auth(api_key: Optional[str]) -> bool:
    if not password:
        return True  # 如果没有设置密码，允许所有请求
    return api_key is not None and compare_digest(api_key, password)

def prepare_request(data: Dict[Any, Any], headers: Dict[str, str], project_id: str, auth_file: str) -> tuple:
    original_model = data.pop('model', None)
    if not original_model:
        raise HTTPException(status_code=400, detail="Model not specified")

    model = vertex_model(original_model)
    
    # 修改：使用选择的 project_id
    url = f"https://{region}-aiplatform.googleapis.com/v1/projects/{project_id}/locations/{region}/publishers/anthropic/models/{model}:streamRawPredict"

    headers.pop('anthropic-version', None)
    new_headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {get_gcloud_token(auth_file)}"  # 修改：使用选择的 auth_file
    }

    data["anthropic_version"] = "vertex-2023-10-16"
    
    return url, new_headers, data

def error_detail(status: str, message: str) -> Dict[str, Any]:
    return {
        "type": "error",
        "error": {
            "type": status,
            "message": message
        }
    }

async def handle_stream_request(url: str, data: Dict[Any, Any], headers: Dict[str, str]):
    client = httpx.AsyncClient()
    
    try:
        # 创建流式传输迭代器，并调用客户端发出请求
        req = client.build_request("POST", url, json=data, headers=headers, timeout=120)
        response = await client.send(req, stream=True)
        
        # 如果状态码不是200，抛出Exception
        if response.status_code != 200:
            await response.aread()
            response.raise_for_status()

        async def generate():
            try:
                is_first_chunk = True
                async for chunk in response.aiter_text():
                    debug_mode and print(chunk, end='', flush=True)
                    yield chunk
                    if is_first_chunk:
                        is_first_chunk = False
                await client.aclose()
                if debug_mode:
                    print("Stream ended.")
            except Exception as e:
                error_content = {"status": "UNKNOWN_ERROR", "message": str(e)}
                yield f"event: error\ndata: {json.dumps(error_content)}\n\n"
                await client.aclose()

        return generate()
    
    except httpx.HTTPStatusError as e:
        error_content = e.response.content
        try:
            error_json = json.loads(error_content)
            error_status = error_json[0]['error'].get('status') or error_json[0]['error'].get('type') or 'UNKNOWN_ERROR'
            error_message = error_json[0]['error'].get('message', 'Unknown error occurred')
        except json.JSONDecodeError:
            error_status = 'UNKNOWN_ERROR'
            error_message = error_content.decode('utf-8')
        await client.aclose()
        print(f"发生错误：{error_detail(error_status, error_message)}")
        return e.response.status_code, error_detail(error_status, error_message)
    except Exception as e:
        print(f"发生未知错误：{str(e)}")
        await client.aclose()
        return 500, error_detail(error_status, error_message)

async def handle_non_stream_request(url: str, data: Dict[Any, Any], headers: Dict[str, str]) -> JSONResponse:
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(url, json=data, headers=headers)
            response.raise_for_status()
            debug_mode and print(response.json()) #debug调试
            return JSONResponse(content=response.json(), status_code=200)
        except httpx.HTTPStatusError as e:
            error_content = e.response.content
            try:
                error_json = json.loads(error_content)
                error_status = error_json[0]['error'].get('status') or error_json[0]['error'].get('type') or 'UNKNOWN_ERROR'
                error_message = error_json[0]['error'].get('message', 'Unknown error occurred')
            except json.JSONDecodeError:
                error_status = 'UNKNOWN_ERROR'
                error_message = error_content.decode('utf-8')
            print(f"发生错误：{error_detail(error_status, error_message)}")
            return JSONResponse(status_code=e.response.status_code, content=error_detail(error_status, error_message))
        except Exception as e:
            return JSONResponse(status_code=500, content=error_detail("internal_error", str(e)))
        
@app.post("/v1/messages")
async def proxy_request(request: Request, x_api_key: Optional[str] = Header(None)):
    if not check_auth(x_api_key):
        raise HTTPException(status_code=401, detail="Unauthorized")

    try:
        data = await request.json()
        debug_mode and print(f"Received request: {data}") #调试模式下打印请求信息
        headers = dict(request.headers)
        
        try:
            project_id, auth_file = load_balance_selector()
        except HTTPException as e:
            print(f"未找到关联的验证文件，请检查配置。")
            return JSONResponse(status_code=500, content=error_detail("internal_error", str(e)))
        
        url, new_headers, processed_data = prepare_request(data, headers, project_id, auth_file)
        
        debug_mode and print(f"Sending request to {url}") #调试模式下打印请求信息
        print(f"Accessing gcloud using project {project_id}") #debug调试输出

        # 判断是否为流式请求
        if processed_data.get('stream', False):
            result = await handle_stream_request(url, processed_data, new_headers)
            
            if isinstance(result, tuple):
                error_code, error_content = result
                return JSONResponse(content=error_content, status_code=error_code)
            else:
                return StreamingResponse(result, media_type='text/event-stream', headers={'X-Accel-Buffering': 'no'})
        else:
            return await handle_non_stream_request(url, processed_data, new_headers)

    except Exception as e:
        print(str(e))
        return JSONResponse(content={"error": str(e)}, status_code=500)
    finally:
        debug_mode and global_selector.print_weights()
