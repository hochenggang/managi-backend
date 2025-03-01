
# managi-backend

一个基于 FastAPI 的网页版 SSH 管理工具，提供用户认证、SSH 连接测试、命令执行等功能，适合用于远程服务器管理。

## 功能特性

- **SSH 连接测试**：支持通过密码或密钥测试 SSH 连接。
- **WEB SSH**：在一个网页上管理多个服务器，数据全部保持在本地。


## 快速开始

### 使用 Docker 镜像

你可以通过 Docker 镜像一行命令快速使用：

```bash
docker run -d -p 18001:18001 hochenggang/managi:0.2.0
```

部署完成后，访问 `http://IP:18001` 即可开始使用。你也可以进一步进行反向代理，配置域名等[DEMO](https://managi.imhcg.cn/)。


---

### 手动部署

#### 安装依赖

确保已安装 Python 3.7+，然后运行以下命令安装依赖：

```bash
pip install fastapi uvicorn paramiko
```

#### 启动应用

```bash
python main.py
```

默认端口为 `18001`，可以通过 `-p` 参数指定端口：

```bash
python main.py -p 8000
```



## 贡献指南

欢迎提交 Issue 和 Pull Request！请确保代码风格一致，并通过所有测试。

## 许可证

本项目基于 [MIT 许可证](LICENSE) 开源。