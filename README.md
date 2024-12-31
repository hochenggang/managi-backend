
# managi-backend

一个基于 FastAPI 的 SSH 管理工具，提供用户认证、SSH 连接测试、命令执行等功能，适合用于远程服务器管理。

## 功能特性

- **用户管理**：支持管理员初始化和用户登录。
- **Token 认证**：基于 JWT 的 Token 认证机制，确保接口安全。
- **SSH 连接测试**：支持通过密码或密钥测试 SSH 连接。
- **命令执行**：在远程服务器上执行命令并返回结果。
- **跨域支持**：内置 CORS 中间件，支持跨域请求。
- **轻量级**：使用 SQLite 作为数据库，无需额外配置。

## 快速开始

### 安装依赖

确保已安装 Python 3.7+，然后运行以下命令安装依赖：

```bash
pip install fastapi uvicorn paramiko
```

### 启动应用

```bash
python main.py
```

默认端口为 `18001`，可以通过 `-p` 参数指定端口：

```bash
python main.py -p 8000
```

### 使用 Docker 镜像

你可以通过 Docker 镜像快速试用：

```bash
docker run -d -p 18001:18001 hochenggang/managi:0.1.0
```

部署完成后，将形如 `http://192.168.1.1:18001` 的后端地址填入前端即可开始使用。前端可以直接访问：[managi-frontend](https://hochenggang.github.io/managi-frontend/)。

### 接口文档

启动应用后，访问以下地址查看接口文档：

- **Swagger UI**: `http://127.0.0.1:18001/docs`
- **ReDoc**: `http://127.0.0.1:18001/redoc`


## 贡献指南

欢迎提交 Issue 和 Pull Request！请确保代码风格一致，并通过所有测试。

## 许可证

本项目基于 [MIT 许可证](LICENSE) 开源。