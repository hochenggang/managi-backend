from typing import List
import time
import json
import io
import asyncio


from fastapi import (
    FastAPI,
    Request,
    Response,
    WebSocket,
)
from fastapi.responses import HTMLResponse
from fastapi.websockets import WebSocketState

from pydantic import BaseModel
import paramiko


# FastAPI 应用
app = FastAPI()


class Node(BaseModel):
    name: str
    ip: str
    port: int
    ssh_username: str
    auth_type: str  # 认证类型：password 或 key
    auth_value: str  # 密码或密钥的值


class NodesCmds(BaseModel):
    nodes: List[Node]
    cmds: List[str]


class CmdsTestResult(BaseModel):
    time_elapsed: float
    success: bool
    output: List[str]
    error: List[str]
    node: Node
    cmds: str


# SSH 连接类
class SSHConnection:
    def __init__(
        self, ip: str, port: int, ssh_username: str, auth_type: str, auth_value: str
    ):
        self.ip = ip
        self.port = port
        self.ssh_username = ssh_username
        self.auth_type = auth_type
        self.auth_value = auth_value
        self.ssh = None

    def __enter__(self):
        """
        创建 SSH 连接。
        """
        self.ssh = paramiko.SSHClient()
        self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        if self.auth_type == "password":
            # 使用密码认证
            self.ssh.connect(
                self.ip,
                port=self.port,
                username=self.ssh_username,
                password=self.auth_value,
                timeout=5,
            )
        elif self.auth_type == "key":
            # 使用密钥认证
            key = paramiko.RSAKey.from_private_key(io.StringIO(self.auth_value))
            self.ssh.connect(
                self.ip, port=self.port, username=self.ssh_username, pkey=key, timeout=5
            )
        else:
            raise ValueError(f"Unsupported auth_type: {self.auth_type}")
        return self.ssh

    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        关闭 SSH 连接。
        """
        if self.ssh:
            self.ssh.close()


@app.post("/api/ssh/test")
def test_ssh_connection(node: Node, cmds: List[str]) -> CmdsTestResult:
    """
    测试 SSH 连接并执行测试命令。
    :param node: 包含节点信息的对象
    :return: 连接耗时、连接是否成功、测试命令输出和错误信息
    """
    start_time = time.time()
    # 将命令列表转换为一个大的命令。备注：整个的命令会在前端按行分割转为列表传输，为未来预留可能的 api 行为变化冗余
    commands = "\n".join(cmds)

    try:
        # 使用 SSHConnection 类测试连接并执行命令
        with SSHConnection(
            node.ip, node.port, node.ssh_username, node.auth_type, node.auth_value
        ) as ssh:
            # 执行测试命令
            stdin, stdout, stderr = ssh.exec_command(commands)
            output = stdout.readlines()
            error = stderr.readlines()
            success = True
    except Exception as e:
        success = False
        output = [""]
        error = [str(e)]
    end_time = time.time()

    # 返回连接耗时、连接是否成功、测试命令输出和错误信息
    return {
        "time_elapsed": round(end_time - start_time, 2),  # 连接耗时，保留两位小数
        "success": success,
        "output": output,
        "error": error,
        "node": {
            "name": node.name,
            "ip": node.ip,
            "ssh_username": node.ssh_username,
            "port": node.port,
            "auth_type": node.auth_type,
            "auth_value": "***",
        },
        "cmds": commands,
    }


@app.get("/api/ping")
def get_ping():
    """
    测试接口是否正常
    返回初始化状态
    """
    global cache_admin_user_count
    cache_api_ping = {}
    cache_api_ping["pong"] = cache_admin_user_count
    return cache_api_ping


@app.get("/")
async def get():
    with open("index.html", "r", encoding="utf-8") as f:
        return HTMLResponse(f.read())


# WebSocket 路由
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()

    try:
        # 接收连接信息
        connection_info = await websocket.receive_text()
        connection_info = json.loads(connection_info)

        # 解析连接信息
        host = connection_info.get("host")
        port = connection_info.get("port", 22)
        username = connection_info.get("username")
        password = connection_info.get("password")
        private_key = connection_info.get("privateKey")

        # 创建 SSH 客户端
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        # 认证方式：密钥或密码
        if private_key:
            private_key_obj = paramiko.RSAKey.from_private_key_file(private_key)
            ssh.connect(host, port=port, username=username, pkey=private_key_obj)
        else:
            ssh.connect(host, port=port, username=username, password=password)

        # 创建 SSH shell 通道
        channel = ssh.invoke_shell()
        channel.setblocking(False)

        # 实时转发数据
        async def forward_output():
            while True:
                if channel.recv_ready():
                    data = channel.recv(1024).decode("utf-8")
                    await websocket.send_text(data)
                await asyncio.sleep(0.1)

        async def forward_input():
            while True:
                data = await websocket.receive_text()
                channel.send(data.encode("utf-8"))

        # 运行任务
        await asyncio.gather(forward_output(), forward_input())

    except Exception as e:
        await websocket.send_text(f"SSH Error: {str(e)}")
    finally:
        if not websocket.client_state == WebSocketState.DISCONNECTED:
            await websocket.close()
        ssh.close()


# OPTION /*
@app.options("/{path:path}")
async def options_handler(path: str):
    """
    跨域请求处理
    """
    return Response(status_code=204)


# 添加 CORS 头
@app.middleware("http")
async def add_cors_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type,Authorization"
    response.headers["Access-Control-Allow-Methods"] = "GET,PUT,POST,DELETE,OPTIONS"
    response.headers["X-VERSION"] = "20241230"
    return response


# 启动应用
if __name__ == "__main__":
    import argparse
    import uvicorn

    parser = argparse.ArgumentParser(description="Run the FastAPI application.")
    parser.add_argument(
        "-p", "--port", type=int, default=18001, help="Port to run the application on."
    )

    # 解析命令行参数
    args = parser.parse_args()
    uvicorn.run(app, host="0.0.0.0", port=args.port)
