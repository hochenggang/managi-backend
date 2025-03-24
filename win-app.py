import time
import threading
import webbrowser
from uvicorn import Config, Server
from app import app
from pystray import Icon, Menu, MenuItem
from PIL import Image


# 启动 Uvicorn 服务器
def run_server():
    config = Config(
        app=app, host="127.0.0.1", port=8000, log_level="warning", access_log=False
    )
    server = Server(config)
    server.run()


# 启动浏览器并打开前端页面
def start_webview():
    # 等待服务器启动完成
    time.sleep(2)
    webbrowser.open("http://127.0.0.1:8000", new=1)


# 托盘图标退出回调函数
def exit_action(icon):
    icon.stop()
    # 停止 FastAPI 服务（通过设置全局变量控制）
    global should_exit
    should_exit = True


# 创建托盘图标
def create_tray_icon():
    # 加载托盘图标（需要准备一个 .ico 文件，例如 "icon.ico"）
    image = Image.open("icon.ico")
    menu = Menu(
        MenuItem("Open in Browser", lambda: webbrowser.open("http://127.0.0.1:8000")),
        MenuItem("Exit", lambda: exit_action(icon)),
    )
    icon = Icon("Managi Tray", image, "Managi Running", menu)
    icon.run()


if __name__ == "__main__":
    # 全局变量，用于控制程序退出
    global should_exit
    should_exit = False

    # 在单独线程中启动 Uvicorn 服务器
    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()

    # 启动浏览器
    start_webview()

    # 启动托盘图标
    tray_thread = threading.Thread(target=create_tray_icon, daemon=True)
    tray_thread.start()

    # 主线程保持运行，直到接收到退出信号
    while not should_exit:
        time.sleep(1)
