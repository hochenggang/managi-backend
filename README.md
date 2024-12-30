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

### 接口文档

启动应用后，访问以下地址查看接口文档：

- **Swagger UI**: `http://127.0.0.1:18001/docs`
- **ReDoc**: `http://127.0.0.1:18001/redoc`

## API 接口

### 1. 初始化管理员

- **URL**: `/api/admin/init`
- **Method**: `POST`
- **Request Body**:
  ```json
  {
    "username": "admin",
    "password": "admin123"
  }
  ```
- **Response**:
  - 成功：`200 OK`
  - 管理员已存在：`403 Forbidden`

### 2. 用户登录

- **URL**: `/api/login`
- **Method**: `POST`
- **Request Body**:
  ```json
  {
    "username": "admin",
    "password": "admin123"
  }
  ```
- **Response**:
  - 成功：
    ```json
    {
      "access_token": "your_token",
      "token_type": "bearer"
    }
    ```
  - 失败：`401 Unauthorized`

### 3. 获取 Token 信息

- **URL**: `/api/token/info`
- **Method**: `GET`
- **Headers**:
  - `Authorization: Bearer your_token`
- **Response**:
  ```json
  {
    "username": "admin",
    "create_at": "1672502400",
    "expire_at": "1672506000"
  }
  ```

### 4. 测试 SSH 连接

- **URL**: `/api/ssh/test`
- **Method**: `POST`
- **Headers**:
  - `Authorization: Bearer your_token`
- **Request Body**:
  ```json
  {
    "name": "test-server",
    "ip": "192.168.1.1",
    "port": 22,
    "ssh_username": "root",
    "auth_type": "password",
    "auth_value": "your_password",
    "cmds": ["ls", "pwd"]
  }
  ```
- **Response**:
  ```json
  {
    "time_elapsed": 0.52,
    "success": true,
    "output": ["file1\n", "file2\n"],
    "error": [],
    "node": {
      "name": "test-server",
      "ip": "192.168.1.1",
      "ssh_username": "root",
      "port": 22,
      "auth_type": "password",
      "auth_value": "***"
    },
    "cmds": "ls\npwd"
  }
  ```

### 5. 测试接口

- **URL**: `/api/ping`
- **Method**: `GET`
- **Response**:
  ```json
  {
    "pong": 1
  }
  ```

## 项目结构

```
.
├── main.py              # 主程序入口
├── README.md            # 项目说明文档
├── management.db        # SQLite 数据库文件，自动生成
```

## 贡献指南

欢迎提交 Issue 和 Pull Request！请确保代码风格一致，并通过所有测试。

## 许可证

本项目基于 [MIT 许可证](LICENSE) 开源。
