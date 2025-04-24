import io
import os
import sys
import time
import json
import asyncio
from enum import Enum
from typing import List, Dict

import paramiko
from pydantic import BaseModel
from fastapi import FastAPI, Request, WebSocket
from starlette.websockets import WebSocketState
from fastapi.responses import HTMLResponse, Response, JSONResponse


app = FastAPI(redoc_url=None, docs_url=None, openapi_url=None)



def get_resource_path(filename: str) -> str:
    """
    Get static file, surport both development and packaging 
    """
    if getattr(sys, "frozen", False):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, filename)


class AuthType(str, Enum):
    PASSWORD = "password"
    KEY = "key"


class Node(BaseModel):
    name: str
    host: str
    port: int
    username: str
    auth_type: AuthType
    auth_value: str


class CmdsTestResult(BaseModel):
    time_elapsed: float
    success: bool
    output: List[str]
    error: List[str]
    node: Node
    cmds: str


class SSHManager:
    def __init__(self, node: Node):
        self.node = node
        self.ssh = None

    def connect(self):
        self.ssh = paramiko.SSHClient()
        self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            if self.node.auth_type == AuthType.PASSWORD:
                self.ssh.connect(
                    self.node.host,
                    port=self.node.port,
                    username=self.node.username,
                    password=self.node.auth_value,
                    timeout=15,
                )
            elif self.node.auth_type == AuthType.KEY:
                key = paramiko.RSAKey.from_private_key(
                    io.StringIO(self.node.auth_value)
                )
                self.ssh.connect(
                    self.node.host,
                    port=self.node.port,
                    username=self.node.username,
                    pkey=key,
                    timeout=15,
                )
            else:
                raise ValueError(f"Unsupported auth_type: {self.node.auth_type}")

            return self

        except Exception as e:
            raise ConnectionError(f"SSH connection failed: {e}")

    def execute_commands(self, commands: List[str]) -> Dict:
        if not self.ssh:
            raise RuntimeError("SSH connection is not established.")
        combined_command = "\n".join(commands)
        stdin, stdout, stderr = self.ssh.exec_command(combined_command)
        return {
            "output": stdout.readlines(),
            "error": stderr.readlines(),
        }

    def close(self):
        if self.ssh:
            self.ssh.close()


@app.post("/api/ssh/test", response_model=CmdsTestResult)
async def test_ssh_connection(node: Node, cmds: List[str]) -> CmdsTestResult:
    """
    exe single cmd
    """
    start_time = time.time()
    try:
        ssh_manager = SSHManager(node).connect()
        result = ssh_manager.execute_commands(cmds)
        success = True
    except Exception as e:
        success = False
        result = {"output": [""], "error": [str(e)]}
    end_time = time.time()

    node.auth_value = "***"
    return CmdsTestResult(
        time_elapsed=round(end_time - start_time, 2),
        success=success,
        output=result["output"],
        error=result["error"],
        node=node,
        cmds="\n".join(cmds),
    )


@app.get("/", response_class=HTMLResponse)
async def get_index():
    """
    Frontend
    """
    html_path = get_resource_path("index.html")
    with open(html_path, "r", encoding="utf-8") as f:
        return HTMLResponse(f.read())


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket for SSH
    """
    await websocket.accept()
    ssh_manager = None
    try:
        raw_node_info = await websocket.receive_text()
        ssh_manager = SSHManager(Node(**json.loads(raw_node_info))).connect()
        channel = ssh_manager.ssh.invoke_shell()
        channel.setblocking(False)

        # data forwarding
        async def forward_output():
            while True:
                if channel.recv_ready():
                    data = channel.recv(1024).decode("utf-8", errors="ignore")
                    await websocket.send_text(data)
                await asyncio.sleep(0.1)

        async def forward_input():
            while True:
                data = await websocket.receive_text()
                channel.send(data.encode("utf-8"))

        # async
        await asyncio.gather(forward_output(), forward_input())

    except Exception:
        pass

    finally:
        if websocket.client_state != WebSocketState.DISCONNECTED:
            await websocket.close()
        if ssh_manager:
            ssh_manager.ssh.close()


@app.middleware("http")
async def add_cors_headers(request: Request, call_next):
    try:
        response: Response = await call_next(request)
    except Exception as e:
        response: JSONResponse = JSONResponse({"error": str(e)}, status_code=500)

    response.headers["Access-Control-Allow-Origin"] = request.headers.get("origin", "*")
    response.headers["Access-Control-Allow-Headers"] = "Content-Type,Authorization"
    response.headers["Access-Control-Allow-Methods"] = "GET,PUT,POST,DELETE,OPTIONS"

    return response


@app.options("/{path:path}")
async def options_handler(path: str):
    """
    CORS OPTIONS 
    """
    return Response(status_code=204)


# 启动应用
if __name__ == "__main__":
    import argparse
    import uvicorn

    parser = argparse.ArgumentParser(description="Managi Backend.")
    parser.add_argument(
        "-p", "--port", type=int, default=18001, help="Port to run the application on."
    )
    args = parser.parse_args()
    print("Server start at:", args)
    uvicorn.run(
        app, host="0.0.0.0", port=args.port, log_level="error", access_log=False
    )
