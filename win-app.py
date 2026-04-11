import os
import sys
import threading
import socket
import webbrowser
import uvicorn
from pystray import Icon, Menu, MenuItem
from PIL import Image

# --- 处理 Nuitka/打包环境下的导入路径 ---
if getattr(sys, "frozen", False) or "nuitka" in sys.modules:
    # 确保程序能找到编译后的模块
    sys.path.append(os.path.dirname(sys.argv[0]))

# 导入 FastAPI 实例
try:
    from app import app
except ImportError as e:
    # 如果打包失败，这里会捕获
    print(f"Import Error: {e}")

# --- 动态获取资源路径 ---
def get_resource_path(filename):
    """
    兼容开发环境、PyInstaller 和 Nuitka 的路径获取方式
    """
    if getattr(sys, "frozen", False):
        # PyInstaller 方式
        base_path = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    elif "__file__" in globals():
        # 普通脚本方式
        base_path = os.path.dirname(os.path.abspath(__file__))
    else:
        # Nuitka 编译后的二进制方式
        base_path = os.path.dirname(sys.argv[0])
        
    return os.path.join(base_path, filename)

def find_available_port(start_port=18001):
    for port in range(start_port, start_port + 100):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", port)) != 0:
                return port
    return start_port


def run_server(port):
    import logging
    
    # 全局禁用所有 logging 级别的输出
    logging.disable(logging.CRITICAL)

    try:
        config = uvicorn.Config(
            app, 
            host="127.0.0.1", 
            port=port, 
            log_config=None,      # 必须设为 None，否则它会加载默认字典并报错
            log_level="critical", # 设为最高级别，确保没有任何输出
            access_log=False,     # 禁用访问日志
            workers=1,
            loop="asyncio"
        )
        server = uvicorn.Server(config)
        server.run()
    except Exception:
        import traceback
        with open("server_error.log", "w", encoding="utf-8") as f:
            traceback.print_exc(file=f)

def create_tray(port):
    icon_path = get_resource_path("icon.ico")
    url = f"http://127.0.0.1:{port}"
    
    image = Image.open(icon_path)
    menu = Menu(
        MenuItem("打开 Managi", lambda: webbrowser.open(url), default=True),
        MenuItem("退出", lambda icon: icon.stop())
    )
    icon = Icon("Managi", image, f"Managi (Port: {port})", menu)
    
    # 自动开启网页
    threading.Timer(1.5, lambda: webbrowser.open(url)).start()
    icon.run()

if __name__ == "__main__":
    # Nuitka onefile 需要这行防止无限自启
    import multiprocessing
    multiprocessing.freeze_support()

    port = find_available_port()
    
    # 启动服务器线程
    t = threading.Thread(target=run_server, args=(port,), daemon=True)
    t.start()

    # 启动托盘 (阻塞主线程)
    create_tray(port)