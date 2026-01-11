import os
import sys
import threading
import socket
import webbrowser
import uvicorn
from pystray import Icon, Menu, MenuItem
from PIL import Image
from app import app

# 获取资源路径
def get_resource_path(filename):
    if getattr(sys, "frozen", False):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, filename)

# 端口发现
def find_available_port(start_port=18001, end_port=19000):
    for port in range(start_port, end_port + 1):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", port)) != 0: # connect_ex 返回 0 表示端口被占用
                return port
    raise RuntimeError("No available ports found")

# 服务器运行
def run_server(port):
    # 使用 uvicorn.Config 配合 Server 类可以实现更精细的控制
    config = uvicorn.Config(app=app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)
    server.run()

class ManagiApp:
    def __init__(self):
        self.port = find_available_port()
        self.url = f"http://127.0.0.1:{self.port}"
        self.icon = None

    def open_url(self):
        webbrowser.open(self.url)

    def quit_app(self, icon):
        icon.stop() # 停止托盘，主线程随之结束，子线程(daemon)会自动销毁

    def run(self):
        # 1. 启动服务器 (子线程 + Daemon)
        server_thread = threading.Thread(target=run_server, args=(self.port,), daemon=True)
        server_thread.start()

        # 2. 延迟打开浏览器
        threading.Timer(1.5, self.open_url).start()

        # 3. 创建并启动托盘图标 (主线程)
        image = Image.open(get_resource_path("icon.ico"))
        menu = Menu(
            MenuItem("打开控制面板", self.open_url, default=True),
            MenuItem("退出程序", self.quit_app),
        )
        self.icon = Icon("Managi", image, f"Managi (Port: {self.port})", menu)
        
        # icon.run 会阻塞主线程，直到调用 icon.stop()
        self.icon.run()

if __name__ == "__main__":
    try:
        managi = ManagiApp()
        managi.run()
    except Exception as e:
        print(f"启动失败: {e}")