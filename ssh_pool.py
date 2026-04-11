import io
import asyncio
import logging
from typing import Optional, Dict
from contextlib import contextmanager
import paramiko
from models import Node, AuthType
from setting import get_ssh_config

logger = logging.getLogger(__name__)


class SSHConnectionError(Exception):
    pass


class SSHConnection:
    def __init__(self, node: Node):
        self.node = node
        self.ssh: Optional[paramiko.SSHClient] = None
        self._lock = asyncio.Lock()

    async def connect(self) -> "SSHConnection":
        config = get_ssh_config()
        self.ssh = paramiko.SSHClient()
        self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        try:
            if self.node.auth_type == AuthType.PASSWORD:
                connect_kwargs = {
                    "hostname": self.node.host,
                    "port": self.node.port,
                    "username": self.node.username,
                    "password": self.node.auth_value,
                    "timeout": config.timeout,
                    "banner_timeout": config.banner_timeout,
                }
            elif self.node.auth_type == AuthType.KEY:
                key = None
                key_classes = [paramiko.RSAKey, paramiko.Ed25519Key, paramiko.ECDSAKey]
                for key_class in key_classes:
                    try:
                        key = key_class.from_private_key(io.StringIO(self.node.auth_value))
                        break
                    except paramiko.SSHException:
                        continue
                if key is None:
                    raise SSHConnectionError("Failed to parse private key")
                connect_kwargs = {
                    "hostname": self.node.host,
                    "port": self.node.port,
                    "username": self.node.username,
                    "pkey": key,
                    "timeout": config.timeout,
                    "banner_timeout": config.banner_timeout,
                }
            else:
                raise SSHConnectionError(f"Unsupported auth_type: {self.node.auth_type}")

            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, lambda: self.ssh.connect(**connect_kwargs))
            self.ssh.get_transport().set_keepalive(config.keepalive_interval)
            return self

        except Exception as e:
            await self.close()
            raise SSHConnectionError(f"SSH connection failed: {e}") from e

    async def execute(self, commands: list[str]) -> Dict[str, list[str]]:
        if not self.ssh:
            raise SSHConnectionError("SSH connection is not established")

        combined_command = "\n".join(commands)
        loop = asyncio.get_running_loop()

        stdin, stdout, stderr = await loop.run_in_executor(
            None, lambda: self.ssh.exec_command(combined_command)
        )

        output_str = (await loop.run_in_executor(None, stdout.read)).decode("utf-8", errors="ignore")
        error_str = (await loop.run_in_executor(None, stderr.read)).decode("utf-8", errors="ignore")

        return {
            "output": output_str.splitlines(),
            "error": error_str.splitlines(),
        }

    async def get_transport(self):
        if not self.ssh or not self.ssh.get_transport():
            raise SSHConnectionError("SSH connection not available")
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self.ssh.get_transport)

    async def close(self) -> None:
        if self.ssh:
            try:
                loop = asyncio.get_running_loop()
                await loop.run_in_executor(None, self.ssh.close)
            except Exception:
                pass
            finally:
                self.ssh = None


class SSHConnectionPool:
    def __init__(self, max_connections: int = 20):
        self.max_connections = max_connections
        self._pools: Dict[str, SSHConnection] = {}
        self._locks: Dict[str, asyncio.Lock] = {}
        self._global_lock = asyncio.Lock()

    def _get_key(self, node: Node) -> str:
        return node.get_connection_key()

    async def get_connection(self, node: Node) -> SSHConnection:
        key = self._get_key(node)

        async with self._global_lock:
            if key not in self._locks:
                self._locks[key] = asyncio.Lock()

        async with self._locks[key]:
            if key in self._pools:
                conn = self._pools[key]
                if conn.ssh and conn.ssh.get_transport() and conn.ssh.get_transport().is_active():
                    return conn
                else:
                    await conn.close()
                    del self._pools[key]

            if len(self._pools) >= self.max_connections:
                oldest_key = next(iter(self._pools))
                oldest_conn = self._pools.pop(oldest_key)
                await oldest_conn.close()

            new_conn = SSHConnection(node)
            await new_conn.connect()
            self._pools[key] = new_conn
            return new_conn

    async def release_connection(self, node: Node) -> None:
        key = self._get_key(node)
        if key in self._pools:
            conn = self._pools.pop(key)
            await conn.close()

    async def close_all(self) -> None:
        for conn in self._pools.values():
            await conn.close()
        self._pools.clear()


connection_pool = SSHConnectionPool()
