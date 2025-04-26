# Managi

Managi is a lightweight, web-based SSH management tool designed for effortless setup and seamless usability, ensuring a hassle-free experience.


> The Windows application is automatically compiled via GitHub Actions, ensuring a transparent build process you can trust. [Download now from the releases page.](https://github.com/hochenggang/managi-backend/releases/)


![CMDS](https://raw.githubusercontent.com/hochenggang/managi-backend/refs/heads/main/docs/previews/page-cmds.jpg)
![SSH](https://raw.githubusercontent.com/hochenggang/managi-backend/refs/heads/main/docs/previews/page-xterm.jpg)
![Finder](https://raw.githubusercontent.com/hochenggang/managi-backend/refs/heads/main/docs/previews/page-finder.jpg)


## Key Features

- **Minimalist Design**: A clean, focused interface with minimal resource consumption, making it suitable for teams and individuals of all sizes.
- **Batch Command Execution**: Execute commands across multiple servers with a single click—such as changing passwords or updating system packages—significantly boosting operational efficiency.
- **Web SSH Terminal**: Manage multiple servers directly from your browser, with all data securely stored locally. Supports SSH connections via both password and key authentication.
- **User-friendly file management**: View, upload, and download files directly in the browser.


## Quick Start

### 1. Deploy to a Server

#### 1.1 Using Docker Image (Recommended)

Deploy Managi quickly using the Docker image:

```bash
docker run -d --network host hochenggang/managi:0.3.3
```

If you prefer to build the image from source, follow these steps:

```bash
git clone https://github.com/hochenggang/managi-backend.git
cd managi-backend
docker build -t managi:0.5.0 .
docker run -d --network host managi:0.5.0
```

Once deployed, access `http://IP:18001` to start using Managi. You can also configure reverse proxies and domain names as needed.

---

#### 1.2 Manual Deployment from Source Code

Ensure Python 3.9+ is installed, then install dependencies and start the service:

```bash
pip install -r requirements.txt
python app.py
```

The default port is `18001`. You can specify a different port using the `-p` parameter:

```bash
python app.py -p 8000
```

For production environments, it's recommended to use process management tools like `systemd` or `supervisord`.

---

#### 1.3 Local Use on Windows

##### 1.3.1 Packaging as an Executable File

On Windows, you can package Managi into a standalone `.exe` file by following these steps:

1. After completing the manual deployment steps, install additional packaging dependencies:
   ```bash
   pip install nuitka pystray pillow
   ```

2. Use Nuitka to compile into a single-file executable:
   ```bash
   nuitka --standalone --onefile --windows-console-mode=disable --windows-icon-from-ico=icon.ico --include-package=PIL --include-package=uvicorn --include-package=fastapi --include-package=pystray --include-data-file=index.html=index.html --include-data-file=icon.ico=icon.ico win-app.py
   ```

   If prompted to install compilers or other components, follow the instructions provided.

3. Once compiled, run the generated `win-app.exe` file. Right-click the tray icon to exit the application.

##### 1.3.2 Download Precompiled Executable

If you prefer not to compile manually, download our precompiled version:

[Releases](https://github.com/hochenggang/managi-backend/releases/)

---

## Contribution Guidelines

We welcome contributions of any kind! If you encounter any issues or have suggestions for improvement, feel free to submit an [Issue](https://github.com/hochenggang/managi-backend/issues) or a [Pull Request](https://github.com/hochenggang/managi-backend/pulls).

---

## License

This project is open-sourced under the [MIT License](LICENSE), allowing you to freely use, modify, and distribute it.

---

## Acknowledgments

The development of Managi would not have been possible without the support of the following outstanding open-source projects and libraries. We extend our heartfelt gratitude to their contributors!

- **[FastAPI](https://fastapi.tiangolo.com/)**: For building efficient, modern Web APIs with a flexible and powerful development experience.
- **[xterm.js](https://xtermjs.org/)**: A web-based terminal emulator component that provides smooth SSH terminal interaction for Managi.
- **[Paramiko](https://www.paramiko.org/)**: A Python implementation of the SSH protocol, offering foundational support for Managi's core functionality.
- Other dependency libraries and tools (see `requirements.txt` or third-party libraries mentioned in this document).

Managi builds upon these open-source projects, integrating and innovating while adhering to the same [MIT License](LICENSE). We look forward to your participation and support!

If you have any questions or suggestions about Managi or related technologies, feel free to open an Issue.
