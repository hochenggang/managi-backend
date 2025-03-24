
##  Managi < 管理你的机

![](https://raw.githubusercontent.com/hochenggang/managi-backend/refs/heads/main/docs/previews/xterm.jpg)

一个网页版 SSH 管理工具，由Python提供 websocket 到 ssh 协议的中继。
便捷的进行 SSH 连接、批量命令执行等功能，最小化设计，及其轻量。


## 功能特性

- **WEB SSH**：在一个网页上管理多个服务器，数据全部保持在本地。支持通过密码或密钥进行 SSH 连接。
- **批量执行命令**：可以一键向多个服务器执行命令，改密码、更新系统软件包，一键即可。


## 快速开始使用

### 1 部署到你的服务器
#### 1.1 使用 Docker 镜像

你可以通过 Docker 镜像一行命令快速使用：

```bash
docker run -d --network host hochenggang/managi:0.3.0
```

或自行拉取源码构建镜像
```
git clone https://github.com/hochenggang/managi-backend.git

docker build -t managi:0.3.0 .

docker run -d --network host managi:0.3.0

```

部署完成后，访问 `http://IP:18001` 即可开始使用。你也可以进一步进行反向代理，配置域名等。


---

#### 1.2 手动部署源代码

确保已安装 Python 3.9+，然后运行以下命令安装依赖：

```bash
pip install -r requirements.txt
python app.py
```

默认端口为 `18001`，可以通过 `-p` 参数指定端口：

```bash
python app.py -p 8000
```
最好是使用进程守护软件来执行。


#### 1.3 Windows 本地使用
##### 1.3.1 手动打包为 exe 本地使用
在 windows 环境下安装前文提及的 python 环境，再执行以下步骤
```
额外安装依赖
pip install fastapi uvicorn nuitka pystray pillow

打包为 exe
nuitka --standalone --onefile --windows-console-mode=disable --windows-icon-from-ico=icon.ico --include-package=PIL --include-package=uvicorn --include-package=fastapi --include-package=pystray --include-data-file=index.html=index.html --include-data-file=icon.ico=icon.ico win-app.py

如果遇到提示需要安装编译器或其它组件，输入 y 执行即可

编译完成后 运行 win-app.exe 即可使用。
可通过右击托盘图标选择 Exit 退出程序。
```

##### 1.3.2 直接下载预打包好的 exe
下载：[win-app-0.3.0.exe](https://github.com/hochenggang/managi-backend/releases/download/0.3.0/win-app.exe) 25.5 MB

## 贡献指南

欢迎提交 Issue 和 Pull Request！

## 许可证

本项目基于 [MIT 许可证](LICENSE) 开源。