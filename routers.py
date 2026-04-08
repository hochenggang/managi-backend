import time
import asyncio
import uuid
from typing import Any, Optional
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState
from fastapi.encoders import jsonable_encoder

from models import (
    Node,
    CmdsTestResult,
    FileOperationRequest,
    FileOperationResponse,
    DownloadMetadata,
    BatchCmdRequest,
)
from ssh_pool import connection_pool
from sftp_client import SFTPClient
from setting import get_websocket_config
from common import safe_json_loads


router = APIRouter()


async def execute_single_command(node: Node, cmds: list[str]) -> CmdsTestResult:
    start_time = time.time()

    async def _execute_task():
        conn = None
        try:
            conn = await connection_pool.get_connection(node)
            result = await conn.execute(cmds)
            return True, result
        except Exception as e:
            return False, {"output": [""], "error": [str(e)]}
        finally:
            if conn:
                await connection_pool.release_connection(node)

    success, result = await _execute_task()
    end_time = time.time()

    node_copy = node.model_copy()
    node_copy.auth_value = "***"
    return CmdsTestResult(
        time_elapsed=round(end_time - start_time, 2),
        success=success,
        output=result["output"],
        error=result["error"],
        node=node_copy,
        cmds="\n".join(cmds),
    )


@router.post("/api/ssh/test", response_model=CmdsTestResult)
async def test_ssh_connection(node: Node, cmds: list[str]) -> CmdsTestResult:
    return await execute_single_command(node, cmds)


@router.post("/api/ssh/batch", response_model=list[CmdsTestResult])
async def batch_execute_commands(request: BatchCmdRequest) -> list[CmdsTestResult]:
    tasks = [execute_single_command(node, request.cmds) for node in request.nodes]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    processed_results = []
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            node = request.nodes[i]
            node_copy = node.model_copy()
            node_copy.auth_value = "***"
            processed_results.append(
                CmdsTestResult(
                    time_elapsed=0.0,
                    success=False,
                    output=[],
                    error=[str(result)],
                    node=node_copy,
                    cmds="\n".join(request.cmds),
                )
            )
        else:
            processed_results.append(result)

    return processed_results


class SFTPSession:
    def __init__(self, websocket: WebSocket):
        self.websocket = websocket
        self.client: Optional[SFTPClient] = None
        self.request_id: Optional[str] = None
        self._pending_requests: dict[str, asyncio.Future] = {}
        self._download_buffer: bytes = b""
        self._download_size: int = 0

    async def connect(self, node: Node) -> None:
        self.client = SFTPClient(node)
        await self.client.connect()

    async def close(self) -> None:
        if self.client:
            await self.client.close()
            self.client = None

    async def send_response(self, data: dict) -> None:
        await self.websocket.send_json(jsonable_encoder(data))

    async def send_binary(self, data: bytes) -> None:
        await self.websocket.send_bytes(data)

    async def handle_request(self, operation: FileOperationRequest) -> dict[str, Any]:
        if not self.client:
            return {"success": False, "message": "SFTP not connected"}

        op = operation.operation.value

        if op == "list":
            return await self.client.list_directory(operation.remote_path)

        elif op == "mkdir":
            return await self.client.create_directory(operation.remote_path)

        elif op == "delete":
            return await self.client.delete_file(operation.remote_path)

        elif op in ("rename", "move"):
            if not operation.new_path:
                return {"success": False, "message": "new_path is required"}
            return await self.client.rename_file(operation.remote_path, operation.new_path)

        elif op == "upload":
            return {"success": True, "message": "Ready to receive binary data", "type": "upload_ready"}

        elif op == "download":
            return await self._handle_download(operation.remote_path)

        else:
            return {"success": False, "message": f"Unknown operation: {op}"}

    async def _handle_download(self, remote_path: str) -> dict[str, Any]:
        result = await self.client.download_file(remote_path)

        if not result["success"]:
            return result

        await self.send_response(DownloadMetadata(
            success=True,
            filename=result["filename"],
            size=result["size"],
        ))

        total_sent = 0
        total_size = result["size"]

        for chunk in result["stream"]:
            await self.send_binary(chunk)
            total_sent += len(chunk)
            progress = int((total_sent / total_size) * 100)
            await self.send_response({
                "type": "progress",
                "operation": "download",
                "progress": progress,
                "sent": total_sent,
                "total": total_size,
            })
            await asyncio.sleep(0)

        return {
            "success": True,
            "message": "Download completed",
            "complete": True,
            "size": total_sent,
        }

    async def handle_binary(self, data: bytes, operation: FileOperationRequest) -> dict[str, Any]:
        if not self.client:
            return {"success": False, "message": "SFTP not connected"}

        if operation.operation.value == "upload":
            result = await self.client.upload_file(operation.remote_path, data)
            return result

        return {"success": False, "message": "Binary data not expected"}


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    ssh_manager = None
    ws_config = get_websocket_config()

    try:
        raw_node_info = await websocket.receive_text()
        node = Node(**safe_json_loads(raw_node_info))

        from ssh_pool import SSHConnection
        ssh_manager = SSHConnection(node)
        await ssh_manager.connect()

        channel = ssh_manager.ssh.invoke_shell(
            term='xterm', width=80, height=24
        )
        channel.setblocking(False)

        async def forward_output():
            while True:
                try:
                    if channel.recv_ready():
                        data = channel.recv(ws_config.max_buffer_size).decode("utf-8", errors="ignore")
                        if not data:
                            break
                        await websocket.send_text(data)
                    else:
                        if channel.exit_status_ready():
                            break
                        await asyncio.sleep(0.05)
                except Exception:
                    break

        async def forward_input():
            try:
                while True:
                    data = await websocket.receive_text()
                    if data.startswith("\x1b[8;"):
                        try:
                            _, dims = data.split(";")
                            rows, cols = dims.split("t")
                            channel.resize(width=int(cols), height=int(rows))
                        except Exception:
                            pass
                    channel.send(data.encode("utf-8"))
            except (WebSocketDisconnect, Exception):
                pass

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
                await ssh_manager.close()
            except Exception:
                pass
        if websocket.client_state != WebSocketState.DISCONNECTED:
            await websocket.close()


@router.websocket("/ws/sftp")
async def sftp_websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    import logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    print("[SFTP] WebSocket accepted")

    session: Optional[SFTPSession] = None
    pending_operation: Optional[FileOperationRequest] = None

    try:
        raw_node_info = await websocket.receive_text()
        logger.info(f"SFTP: Received node info")
        node = Node(**safe_json_loads(raw_node_info))

        session = SFTPSession(websocket)
        await session.connect(node)

        await session.send_response({
            "type": "connected",
            "success": True,
            "message": "SFTP session established"
        })
        logger.info(f"SFTP: Session connected, waiting for messages...")

        while True:
            try:
                message = await websocket.receive()
                logger.info(f"SFTP: Full message: {message}")

                if "text" in message and message.get("text"):
                    data = safe_json_loads(message["text"])
                    logger.info(f"SFTP: Received text data: {data}")

                    if data.get("type") == "resize":
                        continue

                    operation = FileOperationRequest(**data)
                    pending_operation = operation
                    logger.info(f"SFTP: Processing operation: {operation.operation.value}")

                    result = await session.handle_request(operation)
                    logger.info(f"SFTP: Operation result: {result}")

                    if operation.operation.value == "download":
                        pass
                    else:
                        await session.send_response(result)
                        if operation.operation.value != "upload":
                            pending_operation = None

                elif "bytes" in message:
                    logger.info(f"SFTP: Received bytes, length: {len(message.get('bytes', b''))}")
                    if pending_operation and pending_operation.operation.value == "upload":
                        try:
                            result = await session.handle_binary(
                                message["bytes"],
                                pending_operation
                            )
                            logger.info(f"SFTP: Upload result: {result}")
                            await session.send_response(result)
                            pending_operation = None
                        except Exception as e:
                            logger.error(f"SFTP: Upload error: {e}")
                            await session.send_response({
                                "success": False,
                                "message": f"Upload error: {str(e)}"
                            })
                            pending_operation = None
                    else:
                        await session.send_response({
                            "success": False,
                            "message": "No pending upload operation"
                        })

            except Exception as e:
                await session.send_response({
                    "success": False,
                    "message": f"Error: {str(e)}"
                })
                pending_operation = None

    except WebSocketDisconnect:
        pass

    except Exception as e:
        if session and websocket.client_state == WebSocketState.CONNECTED:
            await session.send_response({
                "success": False,
                "message": f"SFTP session error: {str(e)}"
            })

    finally:
        if session:
            await session.close()

        if websocket.client_state != WebSocketState.DISCONNECTED:
            await websocket.close()
