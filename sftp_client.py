import os
import io
from typing import Optional, Dict, Any, BinaryIO, Generator
import paramiko
from models import Node, FileItem
from ssh_pool import SSHConnection, connection_pool
from setting import get_sftp_config


class SFTPClient:
    def __init__(self, node: Node):
        self.node = node
        self.ssh_connection: Optional[SSHConnection] = None
        self.sftp: Optional[paramiko.SFTPClient] = None

    async def connect(self) -> "SFTPClient":
        self.ssh_connection = await connection_pool.get_connection(self.node)
        loop = loop = __import__('asyncio').get_running_loop()
        self.sftp = await loop.run_in_executor(
            None, lambda: self.ssh_connection.ssh.open_sftp()
        )
        return self

    async def upload_file(
        self,
        remote_path: str,
        file_data: bytes | BinaryIO,
        chunk_size: int | None = None
    ) -> Dict[str, Any]:
        config = get_sftp_config()
        chunk_size = chunk_size or config.chunk_size

        if not self.sftp:
            raise RuntimeError("SFTP connection is not established")

        try:
            dirname = os.path.dirname(remote_path)
            if dirname:
                await self._ensure_remote_directory_exists(dirname)

            loop = __import__('asyncio').get_running_loop()

            def _upload():
                with self.sftp.file(remote_path, "wb") as remote_file:
                    remote_file.set_pipelined(True)
                    if isinstance(file_data, bytes):
                        remote_file.write(file_data)
                    else:
                        while True:
                            chunk = file_data.read(chunk_size)
                            if not chunk:
                                break
                            remote_file.write(chunk)

            await loop.run_in_executor(None, _upload)

            file_stat = await loop.run_in_executor(None, lambda: self.sftp.stat(remote_path))
            return {
                "success": True,
                "message": "File uploaded successfully",
                "path": remote_path,
                "size": file_stat.st_size,
            }
        except Exception as e:
            return {"success": False, "message": str(e)}

    async def download_file(
        self, remote_path: str, chunk_size: int | None = None
    ) -> Dict[str, Any]:
        config = get_sftp_config()
        chunk_size = chunk_size or config.download_chunk_size

        if not self.sftp:
            raise RuntimeError("SFTP connection is not established")

        try:
            loop = __import__('asyncio').get_running_loop()
            file_stat = await loop.run_in_executor(None, lambda: self.sftp.stat(remote_path))

            def _create_generator():
                with self.sftp.file(remote_path, "rb") as remote_file:
                    remote_file.prefetch()
                    while True:
                        chunk = remote_file.read(chunk_size)
                        if not chunk:
                            break
                        yield chunk

            return {
                "success": True,
                "stream": _create_generator(),
                "filename": os.path.basename(remote_path),
                "size": file_stat.st_size,
            }
        except Exception as e:
            return {"success": False, "message": str(e)}

    async def delete_file(self, remote_path: str) -> Dict[str, Any]:
        if not self.sftp:
            raise RuntimeError("SFTP connection is not established")

        try:
            loop = __import__('asyncio').get_running_loop()
            file_stat = await loop.run_in_executor(None, lambda: self.sftp.stat(remote_path))

            if file_stat.st_mode & 0o40000 != 0:
                await loop.run_in_executor(None, lambda: self.sftp.rmdir(remote_path))
            else:
                await loop.run_in_executor(None, lambda: self.sftp.remove(remote_path))

            return {
                "success": True,
                "message": "File deleted successfully",
                "path": remote_path,
            }
        except Exception as e:
            return {"success": False, "message": str(e)}

    async def list_directory(self, remote_path: str) -> Dict[str, Any]:
        if not self.sftp:
            raise RuntimeError("SFTP connection is not established")

        try:
            loop = __import__('asyncio').get_running_loop()
            files = await loop.run_in_executor(None, lambda: self.sftp.listdir_attr(remote_path))

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

    async def create_directory(self, remote_path: str) -> Dict[str, Any]:
        if not self.sftp:
            raise RuntimeError("SFTP connection is not established")

        try:
            await self._ensure_remote_directory_exists(remote_path)
            return {
                "success": True,
                "message": "Directory created successfully",
                "path": remote_path,
            }
        except Exception as e:
            return {"success": False, "message": str(e)}

    async def rename_file(self, old_path: str, new_path: str) -> Dict[str, Any]:
        if not self.sftp:
            raise RuntimeError("SFTP connection is not established")

        try:
            new_dir = os.path.dirname(new_path)
            if new_dir:
                await self._ensure_remote_directory_exists(new_dir)

            loop = __import__('asyncio').get_running_loop()
            await loop.run_in_executor(None, lambda: self.sftp.rename(old_path, new_path))

            return {
                "success": True,
                "message": "File renamed/moved successfully",
                "path": new_path,
            }
        except Exception as e:
            return {"success": False, "message": str(e)}

    async def _ensure_remote_directory_exists(self, remote_dir: str) -> None:
        if not self.sftp:
            raise RuntimeError("SFTP connection is not established")

        loop = __import__('asyncio').get_running_loop()

        def _check_and_create():
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
                            pass

        await loop.run_in_executor(None, _check_and_create)

    async def close(self) -> None:
        if self.sftp:
            try:
                loop = __import__('asyncio').get_running_loop()
                await loop.run_in_executor(None, self.sftp.close)
            except Exception:
                pass
            finally:
                self.sftp = None
