import os
import sys
import time
import threading
import webbrowser
import socket
from uvicorn import Config, Server
from pystray import Icon, Menu, MenuItem
from PIL import Image

from app import app


def get_resource_path(filename):
    """获取静态文件路径"""
    if getattr(sys, "frozen", False):  # 检查是否为打包环境
        base_path = sys._MEIPASS
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, filename)


def find_available_port(start_port=18001, end_port=19000):
    """自动查找指定范围内未被占用的端口"""
    for port in range(start_port, end_port + 1):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    raise RuntimeError("未找到可用端口")


# 启动 Uvicorn 服务器
def run_server(port):
    config = Config(
        app=app, host="127.0.0.1", port=port, log_level="warning", access_log=False
    )
    server = Server(config)
    server.run()


# 启动浏览器并打开前端页面
def start_webview(port):
    """等待服务器启动完成并打开浏览器"""
    time.sleep(2)  # 等待服务器启动
    url = f"http://127.0.0.1:{port}"
    webbrowser.open(url, new=1)


# 托盘图标退出回调函数
def exit_action(icon, server_thread: threading.Thread):
    """停止托盘图标并终止服务器线程"""
    icon.stop()
    global should_exit
    should_exit = True
    server_thread.join(timeout=0.5)  # 等待服务器线程优雅退出


# 创建托盘图标
def create_tray_icon(port, server_thread: threading.Thread):
    """创建系统托盘图标"""
    image = Image.open(get_resource_path("icon.ico"))
    url = f"http://127.0.0.1:{port}"
    menu = Menu(
        MenuItem("Open in Browser", lambda: webbrowser.open(url)),
        MenuItem("Exit", lambda: exit_action(icon, server_thread)),
    )
    icon = Icon("Managi Tray", image, "Managi Running", menu)
    icon.run()


if __name__ == "__main__":
    # 全局变量，用于控制程序退出
    global should_exit
    should_exit = False

    # 自动查找未被占用的端口
    port = find_available_port()

    # 在单独线程中启动 Uvicorn 服务器
    server_thread = threading.Thread(target=run_server, args=(port,), daemon=True)
    server_thread.start()

    # 启动浏览器
    start_webview(port)

    # 启动托盘图标
    tray_thread = threading.Thread(
        target=create_tray_icon, args=(port, server_thread), daemon=True
    )
    tray_thread.start()

    # 主线程保持运行，直到接收到退出信号
    while not should_exit:
        time.sleep(0.1)
