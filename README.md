# Managi 

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)

[ENGLISH](./README-en.md)

Managi 是一款轻量级的网页版 SSH 管理工具，轻易搭建，轻松可用，没有心智负担。

> 更新-20250425 ：Windows 应用由 Github Actions 自动编译生成，过程透明，可放心使用。[可前往发布页面下载。](https://github.com/hochenggang/managi-backend/releases/)


![预览图](https://raw.githubusercontent.com/hochenggang/managi-backend/refs/heads/main/docs/previews/xterm.jpg)


## 功能特性

- **WEB SSH 终端**：在浏览器中直接管理多台服务器，所有数据均保存在本地。支持通过密码或密钥进行 SSH 连接。
- **批量命令执行**：一键向多台服务器发送命令，例如修改密码、更新系统软件包等，大幅提升运维效率。
- **极简设计**：界面清爽、功能专注，资源占用极低，适合各种规模的团队和个人使用。


## 快速开始

### 1. 部署到服务器

#### 1.1 使用 Docker 镜像（推荐）

通过 Docker 镜像快速部署 Managi：

```bash
docker run -d --network host hochenggang/managi:0.3.2
```

如果需要从源码构建镜像，可以执行以下步骤：

```bash
git clone https://github.com/hochenggang/managi-backend.git
cd managi-backend
docker build -t managi:0.3.2 .
docker run -d --network host managi:0.3.2
```

部署完成后，访问 `http://IP:18001` 即可开始使用。您还可以配置反向代理和域名以满足实际需求。

---

#### 1.2 手动部署源代码

确保已安装 Python 3.9+，然后运行以下命令安装依赖并启动服务：

```bash
pip install -r requirements.txt
python app.py
```

默认端口为 `18001`，可以通过 `-p` 参数指定其他端口：

```bash
python app.py -p 8000
```

建议使用进程守护工具（如 `systemd` 或 `supervisord`）来管理服务。

---

#### 1.3 Windows 本地使用

##### 1.3.1 手动打包为可执行文件

在 Windows 环境下，您可以按照以下步骤将 Managi 打包为独立的 `.exe` 文件：

1. 在前序手动部署环节基础上，补充安装打包所需依赖：
   ```bash
   pip install nuitka pystray pillow
   ```

2. 使用 Nuitka 打包为单文件可执行程序：
   ```bash
   nuitka --standalone  --onefile --assume-yes-for-downloads --windows-console-mode=disable  --windows-icon-from-ico=icon.ico --include-package=PIL --include-package=uvicorn --include-package=fastapi --include-package=pystray --include-data-file=index.html=index.html --include-data-file=icon.ico=icon.ico win-app.py
   ```

   如果提示需要安装编译器或其他组件，请根据提示完成安装。

3. 编译完成后，运行生成的 `win-app.exe` 文件即可使用。右键点击托盘图标可选择退出程序。

##### 1.3.2 下载预编译的可执行文件

如果您不想手动编译，可以直接下载我们预编译的版本：

[前往发布页](https://github.com/hochenggang/managi-backend/releases/)

---

## 贡献指南

我们欢迎任何形式的贡献！如果您发现任何问题或有改进建议，请随时提交 [Issue](https://github.com/hochenggang/managi-backend/issues) 或 [Pull Request](https://github.com/hochenggang/managi-backend/pulls)。

---

## 许可证

本项目基于 [MIT 许可证](LICENSE) 开源，您可以自由地使用、修改和分发本项目。

---

## 致谢

Managi 的开发离不开以下优秀的开源项目和库的支持，在此向这些项目的贡献者表示衷心感谢！

- **[FastAPI](https://fastapi.tiangolo.com/)**：用于构建高效、现代化的 Web API，提供了灵活且强大的开发体验。
- **[xterm.js](https://xtermjs.org/)**：一个基于 Web 的终端模拟器组件，为 Managi 提供了流畅的 SSH 终端交互体验。
- **[Paramiko](https://www.paramiko.org/)**：一个 Python 实现的 SSH 协议库，为 Managi 的核心功能提供了底层支持。
- 其他依赖库和工具（详见 `requirements.txt` 或本文档提及的第三方库）。

Managi 在这些开源项目的基础上进行了创新与整合，并同样采用 [MIT 许可证](LICENSE) 开源，期待您的参与和支持！

如果您对 Managi 或相关技术有任何疑问或建议，欢迎随时 Issue。
