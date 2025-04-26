import io
import os
import sys
import time
import json
import asyncio
from enum import Enum
from typing import List, Dict, Union, BinaryIO, Optional, Generator, Any
from dataclasses import dataclass

import paramiko
from pydantic import BaseModel, Field
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState
from fastapi.responses import HTMLResponse, Response, JSONResponse
from fastapi.encoders import jsonable_encoder

app = FastAPI(redoc_url=None, docs_url=None, openapi_url=None)


def get_resource_path(filename: str) -> str:
    """
    Get static file, support both development and packaging
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
    name: str = Field(..., description="Node name for display")
    host: str = Field(..., description="Hostname or IP address")
    port: int = Field(22, description="SSH port number")
    username: str = Field(..., description="SSH username")
    auth_type: AuthType = Field(..., description="Authentication type")
    auth_value: str = Field(..., description="Password or private key content")


class CmdsTestResult(BaseModel):
    time_elapsed: float = Field(..., description="Command execution time in seconds")
    success: bool = Field(..., description="Whether the command executed successfully")
    output: List[str] = Field(..., description="Command output lines")
    error: List[str] = Field(..., description="Command error lines")
    node: Node = Field(..., description="Node information")
    cmds: str = Field(..., description="Commands that were executed")


class FileOperationType(str, Enum):
    UPLOAD = "upload"
    DOWNLOAD = "download"
    DELETE = "delete"
    LIST = "list"
    MKDIR = "mkdir"
    RENAME = "rename"
    MOVE = "move"


class FileItem(BaseModel):
    filename: str = Field(..., description="File or directory name")
    size: int = Field(..., description="File size in bytes")
    mode: int = Field(..., description="File mode/permissions")
    is_dir: bool = Field(..., description="Whether the item is a directory")
    mtime: float = Field(..., description="Last modification time")


class FileOperationRequest(BaseModel):
    operation: FileOperationType = Field(..., description="Type of file operation")
    remote_path: str = Field(..., description="Path to the remote file/directory")
    new_path: Optional[str] = Field(
        None, description="New path for rename/move operations"
    )
    content: Optional[str] = Field(
        None, description="Optional content for file creation"
    )


class FileOperationResponse(BaseModel):
    success: bool = Field(..., description="Whether the operation succeeded")
    message: str = Field(..., description="Result message")
    path: Optional[str] = Field(None, description="Affected file/directory path")
    size: Optional[int] = Field(None, description="File size in bytes")
    files: Optional[List[FileItem]] = Field(None, description="Directory listing")
    complete: Optional[bool] = Field(
        None, description="For downloads, indicates completion"
    )


class DownloadMetadata(BaseModel):
    success: bool = Field(..., description="Whether download can proceed")
    filename: Optional[str] = Field(None, description="Name of the file to download")
    size: Optional[int] = Field(None, description="Size of the file in bytes")
    message: Optional[str] = Field(None, description="Error message if success=False")


@dataclass
class SFTPFileChunk:
    data: bytes
    progress: Optional[float] = None


class SSHManager:
    def __init__(self, node: Node):
        self.node = node
        self.ssh: Optional[paramiko.SSHClient] = None

    def connect(self) -> "SSHManager":
        """Establish SSH connection"""
        self.ssh = paramiko.SSHClient()
        self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        try:
            if self.node.auth_type == AuthType.PASSWORD:
                self.ssh.connect(
                    hostname=self.node.host,
                    port=self.node.port,
                    username=self.node.username,
                    password=self.node.auth_value,
                    timeout=15,
                    banner_timeout=15,
                )
            elif self.node.auth_type == AuthType.KEY:
                key = paramiko.RSAKey.from_private_key(io.StringIO(self.node.auth_value))
                self.ssh.connect(
                    hostname=self.node.host,
                    port=self.node.port,
                    username=self.node.username,
                    pkey=key,
                    timeout=15,
                    banner_timeout=15,
                )
            else:
                raise ValueError(f"Unsupported auth_type: {self.node.auth_type}")
            return self
        except Exception as e:
            self.close()
            raise ConnectionError(f"SSH connection failed: {e}") from e

    def execute_commands(self, commands: List[str]) -> Dict[str, List[str]]:
        """Execute commands on the remote host"""
        if not self.ssh:
            raise RuntimeError("SSH connection is not established")
        
        combined_command = "\n".join(commands)
        stdin, stdout, stderr = self.ssh.exec_command(combined_command)
        return {
            "output": stdout.read().decode("utf-8", errors="ignore").splitlines(),
            "error": stderr.read().decode("utf-8", errors="ignore").splitlines(),
        }

    def close(self) -> None:
        """Close SSH connection"""
        if self.ssh:
            self.ssh.close()
            self.ssh = None


class SFTPManager(SSHManager):
    def __init__(self, node: Node):
        super().__init__(node)
        self.sftp: Optional[paramiko.SFTPClient] = None

    def connect(self) -> "SFTPManager":
        """Establish SFTP connection"""
        super().connect()
        try:
            self.sftp = self.ssh.open_sftp()
            return self
        except Exception as e:
            self.close()
            raise ConnectionError(f"SFTP connection failed: {e}") from e

    def upload_file(
        self,
        remote_path: str,
        file_data: Union[bytes, BinaryIO],
        chunk_size: int = 8192,
    ) -> Dict[str, Any]:
        """Upload file to remote host"""
        if not self.sftp:
            raise RuntimeError("SFTP connection is not established")

        try:
            dirname = os.path.dirname(remote_path)
            if dirname:
                self._ensure_remote_directory_exists(dirname)

            with self.sftp.file(remote_path, "wb") as remote_file:
                if isinstance(file_data, bytes):
                    remote_file.write(file_data)
                else:
                    while True:
                        chunk = file_data.read(chunk_size)
                        if not chunk:
                            break
                        remote_file.write(chunk)

            file_stat = self.sftp.stat(remote_path)
            return {
                "success": True,
                "message": "File uploaded successfully",
                "path": remote_path,
                "size": file_stat.st_size,
            }
        except Exception as e:
            return {"success": False, "message": str(e)}

    def download_file(
        self, remote_path: str, chunk_size: int = 8192
    ) -> Dict[str, Any]:
        """Download file from remote host"""
        if not self.sftp:
            raise RuntimeError("SFTP connection is not established")

        try:
            file_stat = self.sftp.stat(remote_path)
            
            def file_generator() -> Generator[bytes, None, None]:
                with self.sftp.file(remote_path, "rb") as remote_file:
                    while True:
                        chunk = remote_file.read(chunk_size)
                        if not chunk:
                            break
                        yield chunk

            return {
                "success": True,
                "stream": file_generator(),
                "filename": os.path.basename(remote_path),
                "size": file_stat.st_size,
            }
        except Exception as e:
            return {"success": False, "message": str(e)}

    def delete_file(self, remote_path: str) -> Dict[str, Any]:
        """Delete remote file"""
        if not self.sftp:
            raise RuntimeError("SFTP connection is not established")

        try:
            file_stat = self.sftp.stat(remote_path)
            if file_stat.st_mode & 0o40000 != 0:  # Check if it's a directory
                self.sftp.rmdir(remote_path)
            else:
                self.sftp.remove(remote_path)
            return {
                "success": True,
                "message": "File deleted successfully",
                "path": remote_path,
            }
        except Exception as e:
            return {"success": False, "message": str(e)}

    def list_directory(self, remote_path: str) -> Dict[str, Any]:
        """List contents of remote directory"""
        if not self.sftp:
            raise RuntimeError("SFTP connection is not established")

        try:
            files = self.sftp.listdir_attr(remote_path)
            result = []
            for file in files:
                result.append(
                    FileItem(
                        filename=file.filename,
                        size=file.st_size,
                        mode=file.st_mode,
                        is_dir=file.st_mode & 0o40000 != 0,
                        mtime=file.st_mtime,
                    )
                )
            return {
                "success": True,
                "files": result,
                "path": remote_path,
                "message": "Directory listed successfully",
            }
        except Exception as e:
            return {"success": False, "message": str(e)}

    def create_directory(self, remote_path: str) -> Dict[str, Any]:
        """Create remote directory"""
        if not self.sftp:
            raise RuntimeError("SFTP connection is not established")

        try:
            self._ensure_remote_directory_exists(remote_path)
            return {
                "success": True,
                "message": "Directory created successfully",
                "path": remote_path,
            }
        except Exception as e:
            return {"success": False, "message": str(e)}

    def rename_file(self, old_path: str, new_path: str) -> Dict[str, Any]:
        """Rename or move remote file/directory"""
        if not self.sftp:
            raise RuntimeError("SFTP connection is not established")

        try:
            # Ensure parent directory exists for new path
            new_dir = os.path.dirname(new_path)
            if new_dir:
                self._ensure_remote_directory_exists(new_dir)
                
            self.sftp.rename(old_path, new_path)
            return {
                "success": True,
                "message": "File renamed/moved successfully",
                "path": new_path,
            }
        except Exception as e:
            return {"success": False, "message": str(e)}

    def _ensure_remote_directory_exists(self, remote_dir: str) -> None:
        """Recursively create remote directory if it doesn't exist"""
        if not self.sftp:
            raise RuntimeError("SFTP connection is not established")

        try:
            self.sftp.stat(remote_dir)
        except IOError:
            parts = remote_dir.split("/")
            current_dir = ""
            for part in parts:
                if not part:
                    continue
                current_dir += "/" + part
                try:
                    self.sftp.stat(current_dir)
                except IOError:
                    self.sftp.mkdir(current_dir)

    def close(self) -> None:
        """Close SFTP connection"""
        if self.sftp:
            self.sftp.close()
            self.sftp = None
        super().close()


async def handle_sftp_operation(
    sftp_manager: SFTPManager,
    operation: FileOperationRequest,
    websocket: WebSocket,
) -> None:
    """Handle individual SFTP operation"""
    try:
        if operation.operation == FileOperationType.UPLOAD:
            file_data = await websocket.receive_bytes()
            result = sftp_manager.upload_file(operation.remote_path, file_data)
            await websocket.send_json(jsonable_encoder(result))

        elif operation.operation == FileOperationType.DOWNLOAD:
            result = sftp_manager.download_file(operation.remote_path)
            if not result["success"]:
                await websocket.send_json(jsonable_encoder(result))
                return

            # Send metadata first
            metadata = DownloadMetadata(
                success=True,
                filename=result["filename"],
                size=result["size"],
            )
            await websocket.send_json(jsonable_encoder(metadata))

            # Stream file content
            for chunk in result["stream"]:
                await websocket.send_bytes(chunk)

            # Send completion marker
            await websocket.send_json(
                jsonable_encoder(
                    FileOperationResponse(
                        success=True,
                        message="File download completed",
                        complete=True,
                    )
                )
            )

        elif operation.operation == FileOperationType.LIST:
            result = sftp_manager.list_directory(operation.remote_path)
            await websocket.send_json(jsonable_encoder(result))

        elif operation.operation == FileOperationType.DELETE:
            result = sftp_manager.delete_file(operation.remote_path)
            await websocket.send_json(jsonable_encoder(result))

        elif operation.operation == FileOperationType.MKDIR:
            result = sftp_manager.create_directory(operation.remote_path)
            await websocket.send_json(jsonable_encoder(result))

        elif operation.operation in (FileOperationType.RENAME, FileOperationType.MOVE):
            if not operation.new_path:
                raise ValueError("new_path is required for rename/move operation")
            result = sftp_manager.rename_file(operation.remote_path, operation.new_path)
            await websocket.send_json(jsonable_encoder(result))

        else:
            await websocket.send_json(
                jsonable_encoder(
                    FileOperationResponse(
                        success=False,
                        message=f"Unsupported operation: {operation.operation}",
                    )
                )
            )

    except Exception as e:
        await websocket.send_json(
            jsonable_encoder(
                FileOperationResponse(
                    success=False,
                    message=f"Operation failed: {str(e)}",
                )
            )
        )


@app.websocket("/ws/sftp")
async def sftp_websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for SFTP operations"""
    await websocket.accept()
    sftp_manager: Optional[SFTPManager] = None

    try:
        # 1. Receive and parse node information
        raw_node_info = await websocket.receive_text()
        node = Node(**json.loads(raw_node_info))
        
        # 2. Establish SFTP connection
        sftp_manager = SFTPManager(node).connect()
        
        # 3. Main operation loop
        while True:
            operation_data = await websocket.receive_text()
            operation = FileOperationRequest(**json.loads(operation_data))
            
            await handle_sftp_operation(sftp_manager, operation, websocket)

    except WebSocketDisconnect:
        # Normal client disconnect
        pass
        
    except json.JSONDecodeError as e:
        await websocket.send_json(
            jsonable_encoder(
                FileOperationResponse(
                    success=False,
                    message=f"Invalid JSON data: {str(e)}",
                )
            )
        )
        
    except Exception as e:
        await websocket.send_json(
            jsonable_encoder(
                FileOperationResponse(
                    success=False,
                    message=f"SFTP session error: {str(e)}",
                )
            )
        )
        
    finally:
        # Clean up resources
        if websocket.client_state != WebSocketState.DISCONNECTED:
            await websocket.close()
            
        if sftp_manager:
            sftp_manager.close()
            

@app.get("/", response_class=HTMLResponse)
async def get_index():
    """
    Frontend
    """
    html_path = get_resource_path("index.html")
    with open(html_path, "r", encoding="utf-8") as f:
        return HTMLResponse(f.read())


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
