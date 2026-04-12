# Managi

Managi 是一款轻量级网页版 SSH 管理工具。设计简洁易用，支持批量执行命令，简单的SFTP文件管理，SSH终端，让您的运维工作更加轻松便捷。

![CMDS](./docs/previews/page-cmds.jpg)
![SSH](./docs/previews/page-xterm.jpg)
![Finder](./docs/previews/page-finder.jpg)


## 快速开始

### 1. 本机运行客户端

#### Windows 桌面端

直接下载预编译的 `.exe` 文件：

> Windows 应用程序通过 GitHub Actions 自动编译，构建过程透明可信。[点击下载](https://github.com/hochenggang/managi-backend/releases/)

或自行编译：

```bash
git clone https://github.com/hochenggang/managi-backend.git
cd managi-backend
pip install -r requirements.txt
pip install nuitka pystray pillow
nuitka --standalone --onefile --windows-console-mode=disable --windows-icon-from-ico=icon.ico --include-package=PIL --include-package=uvicorn --include-package=fastapi --include-package=pystray --include-data-file=index.html=index.html --include-data-file=icon.ico=icon.ico win-app.py
```

### 2. 服务器运行网页版

#### Docker 部署

```bash
# 拉取源码构建
git clone https://github.com/hochenggang/managi-backend.git
cd managi-backend
docker build -t managi:latest .

# 禁用 BasicAuth
docker run -d --network host -e MANAGI_BASICAUTH_ENABLED=false managi:latest

# 自定义端口和 BasicAuth
docker run -d --network host \
  -e MANAGI_PORT=8080 \
  -e MANAGI_BASICAUTH_ENABLED=true \
  -e MANAGI_BASICAUTH_USERNAME=admin \
  -e MANAGI_BASICAUTH_PASSWORD=your_password \
  managi:latest

```


## 核心特性

- **简洁设计**：界面简洁直观，资源占用低，适合各种规模的团队和个人使用。
- **批量命令执行**：一键在多台服务器上执行命令，如批量修改密码、更新系统包，显著提升运维效率。
- **网页 SSH 终端**：直接在浏览器中管理多台服务器，所有数据安全存储在本地。支持密码和密钥认证。
- **便捷的文件管理**：直接在浏览器中查看、上传和下载文件。

## 配置说明

### ServerConfig

| 环境变量 | 默认值 | 说明 |
|---------------------|---------|-------------|
| `MANAGI_HOST` | 0.0.0.0 | 绑定地址 |
| `MANAGI_PORT` | 18001 | 服务端口 |
| `MANAGI_LOG_LEVEL` | error | 日志级别 |
| `MANAGI_SSH_TIMEOUT` | 15 | SSH 超时秒数 |
| `MANAGI_KEEPALIVE` | 30 | Keepalive 间隔秒数 |

### BasicAuthConfig

| 环境变量 | 默认值 | 说明 |
|---------------------|---------|-------------|
| `MANAGI_BASICAUTH_ENABLED` | true | 启用 BasicAuth |
| `MANAGI_BASICAUTH_USERNAME` | admin | BasicAuth 用户名 |
| `MANAGI_BASICAUTH_PASSWORD` | admin | BasicAuth 密码 |


## 贡献指南

我们欢迎任何形式的贡献！如果您遇到问题或有改进建议，欢迎提交 [Issue](https://github.com/hochenggang/managi-backend/issues) 或 [Pull Request](https://github.com/hochenggang/managi-backend/pulls)。

## 许可证

本项目基于 [MIT 许可证](LICENSE) 开源，您可以自由使用、修改和分发。

## 致谢

Managi 的开发离不开以下优秀开源项目和库的支持，在此向所有贡献者表示衷心的感谢！

- **[FastAPI](https://fastapi.tiangolo.com/)**：构建高效、现代 Web API 的框架，提供灵活而强大的开发体验。
- **[xterm.js](https://xtermjs.org/)**：网页版终端模拟器组件，为 Managi 提供流畅的 SSH 终端交互体验。
- **[Paramiko](https://www.paramiko.org/)**：Python 实现的 SSH 协议，为 Managi 的核心功能提供基础支持。
- 其他依赖库和工具（详见 `requirements.txt` 或本文档中提及的第三方库）。

Managi 基于这些开源项目构建，在遵循 [MIT 许可证](LICENSE) 的同时进行整合和创新。期待您的参与和支持！

如果您对 Managi 或相关技术有任何问题和建议，欢迎提交 Issue。
