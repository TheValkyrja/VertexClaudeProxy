# 施工中：
新代码尚未经过充分测试，故尚未进行全平台的二进制文件打包。
使用python环境运行的用户可先行进行测试。

待确保无大问题之后将会打包发布可运行文件和docker文件。

*新功能：报错处理、多账号负载均衡

可在project_id中填入多个project_id，使用","进行分隔。
当auth.json存在时，应用将自动使用列表中第一个project_id，使用auth.json进行验证。

若要启用多账号模式，将每个服务账号的json文件重命名为对应project_id.json放置于auth文件夹内，即启用多账号模式，应用会随机使用列表中的project_id对应的json文件进行验证和访问。（注意此模式下不要让auth文件夹内存在auth.json文件，不然默认只使用第一个project.）

# VertexClaudeProxy
将标准Anthropic Claude请求转发至VertexAI Claude的代理服务器应用，使用Fastapi。
支持Claude 3.5 sonnet, Claude 3 Opus/Sonnet/Haiku on Vertex AI

## 这个项目是做什么的？
这个项目在本地架设Fastapi服务器，将发送至此服务器的标准Anthropic请求处理模型名后使用标准HTTP请求将请求转发至Vertex AI Claude。

### Usage
#### 准备工作：
1.一个已启用结算账号或存在可用额度的GCP账号，且已启用Vertex AI API。（本步骤不提供教程）  
2.一个GCP VertexAI服务账号。  
3.一台可访问对应地区GCP资源的主机。  
4.(可选)Docker&Docker Compose或Python运行环境。（基于你的安装方式及系统）


#### 开始使用

##### 1. 必要前置条件：为GCP账号启用Vertex AI User用于验证：

<details>
  <summary>点击展开</summary>

**为避免不必要的安全性问题，本应用强烈建议使用服务账号限制应用和服务器对GCP的访问。**

1.点击GCP左上角Google图标，点击左上角导航栏，导航至IAM管理-服务账号
![F $O }NYM{J`{C0{90L){2J](https://github.com/TheValkyrja/Anthropic2Vertex/assets/45366459/e6a57671-dad8-4b7a-9dfd-20d62d7a35a3)  

2.创建服务账号  
![)E 7@C_U2{90I2VJUKM}FD](https://github.com/TheValkyrja/Anthropic2Vertex/assets/45366459/469d8314-cdc8-4d48-9299-9505d1fde7eb)

3.随意填写名字和ID，创建，搜索并为其选择Vertex AI User角色,完成创建。
![7(E GI8MUJNT `K CZTN15](https://github.com/TheValkyrja/Anthropic2Vertex/assets/45366459/c179b76d-7e04-4e43-90f2-bd789287bfcc)
![VR33I92N0Z0AANG 0T~)EGW](https://github.com/TheValkyrja/Anthropic2Vertex/assets/45366459/a561ce41-9aaa-417b-9d39-1312875e35fd)

4.点击右侧管理密钥。
![$ _7K@S1CN`O DYLC6HS$X](https://github.com/TheValkyrja/Anthropic2Vertex/assets/45366459/f38c9436-466a-42fe-b69b-fb80c1aabd46)

5.添加密钥-创建密钥-创建。
![` 8}9{$AO~Q5S1P$G3 PU4X](https://github.com/TheValkyrja/Anthropic2Vertex/assets/45366459/572b3e46-47ac-4201-a320-1fbfeacc3e93)

6.浏览器将会自动下载一个密钥文件，你不需要编辑它，只需要妥善保存。

**请像保护密码一样妥善保管此文件！！**

一旦遗失，无法重新下载，泄露将产生严重安全问题。
</details>

##### 2.下载、解压文件。  

##### 3.配置文件。  

<details>
  <summary>点击展开</summary>

导航至解压的文件夹。  

重命名.env.example为.env，并使用文本编辑器编辑.env文件：

将端口，监听地址修改为你的服务器监听地址（默认127.0.0.1:5000）  
并依照需求设置密码（为空即不认证，慎选）。

PROJECT ID可以在GCP首页找到，设置为你自己的ProjectID.
![UZOJG8RSZ HJSFKEU01DJO9](https://github.com/TheValkyrja/Anthropic2Vertex/assets/45366459/f027c76f-b6dd-43eb-96c9-1ffe629de509)

访问区域填写为为你有权访问、且Claude on Vertex正常服务的地区，默认us-east5。

最后，将第一步中下载下来的xxxxxxxxxx.json密钥文件重命名为auth.json，放入文件夹下auth目录中。

</details>

##### 4.安装并启动


<details>
  
  <summary>使用Python运行</summary>
  
  本方法的优点：  
  1. 所需应用文件体积极小  
  2. 可扩展性与自定义性强  
  3. 代码运行内容安全透明  

  本方法的缺点：
  1. 需要Python运行环境（最好是python3）与Pip包管理器
  2. python依赖与运行库可能占用空间较大。
  3. 对于不同系统兼容性不定。

**如果你看不懂这些内容在说什么，请返回尝试前两种运行方法！**

1. 确保你的系统已经安装了python3与pip3包管理器  
以Ubuntu为例：  
安装python与pip
```
sudo apt-get update
sudo apt install python3 python3-pip
```

2. 安装依赖。  
导航至应用文件夹，运行
```
pip install -r requirements.txt
```

3. 运行。
```
python3 main.py
```

4. 删除目录下main与main.exe文件进一步节省空间。  
注：照做这步后将无法使用二进制文件启动。确保你知道你在做什么，否则请无视。

应用将会监听于.env文件中设置的对应地址与端口，使用方式与docker运行一样。

</details>
