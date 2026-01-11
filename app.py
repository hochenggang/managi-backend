import io
import os
import sys
import time
import json
import asyncio
import socket
import functools
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


# --- Async Helper ---
async def run_in_thread(func, *args, **kwargs):
    """
    Run synchronous blocking functions in a separate thread
    to prevent blocking the main asyncio event loop.
    """
    loop = asyncio.get_running_loop()
    partial_func = functools.partial(func, *args, **kwargs)
    return await loop.run_in_executor(None, partial_func)


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
            
            # [Stability Fix] KeepAlive to prevent connection drop
            self.ssh.get_transport().set_keepalive(30)
            return self
        except Exception as e:
            self.close()
            raise ConnectionError(f"SSH connection failed: {e}") from e

    def execute_commands(self, commands: List[str]) -> Dict[str, List[str]]:
        """Execute commands on the remote host"""
        if not self.ssh:
            raise RuntimeError("SSH connection is not established")
        
        combined_command = "\n".join(commands)
        # exec_command returns (stdin, stdout, stderr)
        stdin, stdout, stderr = self.ssh.exec_command(combined_command)
        
        # Determine exit status to ensure command finished before reading
        # This is blocking, so it must be run in a thread (handled by caller)
        output_str = stdout.read().decode("utf-8", errors="ignore")
        error_str = stderr.read().decode("utf-8", errors="ignore")
        
        return {
            "output": output_str.splitlines(),
            "error": error_str.splitlines(),
        }

    def close(self) -> None:
        """Close SSH connection"""
        if self.ssh:
            try:
                self.ssh.close()
            except Exception:
                pass
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
        chunk_size: int = 32768, # Increased chunk size for better performance
    ) -> Dict[str, Any]:
        """Upload file to remote host"""
        if not self.sftp:
            raise RuntimeError("SFTP connection is not established")

        try:
            dirname = os.path.dirname(remote_path)
            if dirname:
                self._ensure_remote_directory_exists(dirname)

            # Prefetch set to False can sometimes help with upload stability on some servers
            with self.sftp.file(remote_path, "wb") as remote_file:
                # Optimized write buffer
                remote_file.set_pipelined(True) 
                
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
        self, remote_path: str, chunk_size: int = 32768
    ) -> Dict[str, Any]:
        """Download file from remote host"""
        if not self.sftp:
            raise RuntimeError("SFTP connection is not established")

        try:
            file_stat = self.sftp.stat(remote_path)
            
            def file_generator() -> Generator[bytes, None, None]:
                with self.sftp.file(remote_path, "rb") as remote_file:
                    # Optimized read buffer
                    remote_file.prefetch()
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
            # listdir_attr is better than listdir
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
                    try:
                        self.sftp.mkdir(current_dir)
                    except IOError: 
                        # Race condition handling or permission issue
                        pass 

    def close(self) -> None:
        """Close SFTP connection"""
        if self.sftp:
            try:
                self.sftp.close()
            except Exception:
                pass
            self.sftp = None
        super().close()


async def handle_sftp_operation(
    sftp_manager: SFTPManager,
    operation: FileOperationRequest,
    websocket: WebSocket,
) -> None:
    """Handle individual SFTP operation"""
    try:
        # [Concurrency Fix] All sftp_manager calls are wrapped in run_in_thread
        # to prevent blocking the asyncio loop.
        
        if operation.operation == FileOperationType.UPLOAD:
            file_data = await websocket.receive_bytes()
            result = await run_in_thread(sftp_manager.upload_file, operation.remote_path, file_data)
            await websocket.send_json(jsonable_encoder(result))

        elif operation.operation == FileOperationType.DOWNLOAD:
            # Initial stat is blocking, run in thread
            result = await run_in_thread(sftp_manager.download_file, operation.remote_path)
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
            # Note: We iterate in main loop, but read calls inside generator 
            # are unfortunately blocking. For true non-blocking download, 
            # we'd need to restructure the generator to read in thread pool.
            # However, sending bytes is async, which gives some breathing room.
            for chunk in result["stream"]:
                await websocket.send_bytes(chunk)
                # Yield control explicitly to let other tasks run during heavy downloads
                await asyncio.sleep(0)

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
            result = await run_in_thread(sftp_manager.list_directory, operation.remote_path)
            await websocket.send_json(jsonable_encoder(result))

        elif operation.operation == FileOperationType.DELETE:
            result = await run_in_thread(sftp_manager.delete_file, operation.remote_path)
            await websocket.send_json(jsonable_encoder(result))

        elif operation.operation == FileOperationType.MKDIR:
            result = await run_in_thread(sftp_manager.create_directory, operation.remote_path)
            await websocket.send_json(jsonable_encoder(result))

        elif operation.operation in (FileOperationType.RENAME, FileOperationType.MOVE):
            if not operation.new_path:
                raise ValueError("new_path is required for rename/move operation")
            result = await run_in_thread(sftp_manager.rename_file, operation.remote_path, operation.new_path)
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
        
        # 2. Establish SFTP connection (Async wrapper)
        # Creating connection involves network IO, must be offloaded
        sftp_manager = SFTPManager(node)
        await run_in_thread(sftp_manager.connect)
        
        # 3. Main operation loop
        while True:
            operation_data = await websocket.receive_text()
            operation = FileOperationRequest(**json.loads(operation_data))
            
            await handle_sftp_operation(sftp_manager, operation, websocket)

    except WebSocketDisconnect:
        pass
        
    except json.JSONDecodeError as e:
        if websocket.client_state == WebSocketState.CONNECTED:
            await websocket.send_json(
                jsonable_encoder(
                    FileOperationResponse(
                        success=False,
                        message=f"Invalid JSON data: {str(e)}",
                    )
                )
            )
        
    except Exception as e:
        if websocket.client_state == WebSocketState.CONNECTED:
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
        if sftp_manager:
            # Closing might involve sending a packet, do it safely
            try:
                await run_in_thread(sftp_manager.close)
            except Exception:
                pass
        
        if websocket.client_state != WebSocketState.DISCONNECTED:
            await websocket.close()
            

@app.get("/", response_class=HTMLResponse)
async def get_index():
    """
    Frontend
    """
    html_path = get_resource_path("index.html")
    # Async file read for slightly better concurrency on high load
    if os.path.exists(html_path):
        with open(html_path, "r", encoding="utf-8") as f:
            return HTMLResponse(f.read())
    return HTMLResponse("<h1>Index file not found</h1>", status_code=404)


@app.post("/api/ssh/test", response_model=CmdsTestResult)
async def test_ssh_connection(node: Node, cmds: List[str]) -> CmdsTestResult:
    """
    exe single cmd
    """
    start_time = time.time()
    
    # [Concurrency Fix] Define a task to run in thread pool
    def _execute_task():
        manager = SSHManager(node)
        try:
            manager.connect()
            res = manager.execute_commands(cmds)
            return True, res
        except Exception as e:
            return False, {"output": [""], "error": [str(e)]}
        finally:
            manager.close()

    # Run blocking SSH task in executor
    success, result = await run_in_thread(_execute_task)
    
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
        node = Node(**json.loads(raw_node_info))
        
        # Connect in thread
        ssh_manager = SSHManager(node)
        await run_in_thread(ssh_manager.connect)
        
        channel = ssh_manager.ssh.invoke_shell(
            term='xterm', width=80, height=24
        )
        channel.setblocking(False)

        # data forwarding
        async def forward_output():
            while True:
                try:
                    if channel.recv_ready():
                        data = channel.recv(4096).decode("utf-8", errors="ignore")
                        if not data:
                            break
                        await websocket.send_text(data)
                    else:
                        # Check if connection is closed
                        if channel.exit_status_ready():
                             break
                        await asyncio.sleep(0.05) # Reduced sleep for better responsiveness
                except socket.timeout:
                    pass
                except Exception:
                    break

        async def forward_input():
            try:
                while True:
                    data = await websocket.receive_text()
                    # Resizing terminal logic could go here if frontend supports it
                    channel.send(data.encode("utf-8"))
            except (WebSocketDisconnect, Exception):
                pass

        # async
        done, pending = await asyncio.wait(
            [asyncio.create_task(forward_output()), asyncio.create_task(forward_input())],
            return_when=asyncio.FIRST_COMPLETED
        )
        for task in pending:
            task.cancel()

    except Exception:
        pass

    finally:
        if ssh_manager:
            try:
                ssh_manager.close()
            except Exception:
                pass
        if websocket.client_state != WebSocketState.DISCONNECTED:
            await websocket.close()


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