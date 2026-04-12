import os
import asyncio
from dataclasses import dataclass, field
from typing import Optional
from functools import partial


@dataclass
class SSHConfig:
    timeout: int = 15
    banner_timeout: int = 15
    keepalive_interval: int = 30
    connection_timeout: int = 15


@dataclass
class WebSocketConfig:
    heartbeat_interval: int = 10000
    heartbeat_timeout: int = 10000
    max_buffer_size: int = 4096
    ping_interval: int = 30


@dataclass
class SFTPConfig:
    chunk_size: int = 32768
    download_chunk_size: int = 65536
    upload_buffer_size: int = 32768


@dataclass
class ServerConfig:
    host: str = "0.0.0.0"
    port: int = 18001
    log_level: str = "error"
    access_log: bool = False
    reload: bool = False
    workers: int = 1


@dataclass
class BasicAuthConfig:
    enabled: bool = False
    username: str = "admin"
    password: str = "admin123"


@dataclass
class AppConfig:
    server: ServerConfig = field(default_factory=ServerConfig)
    ssh: SSHConfig = field(default_factory=SSHConfig)
    websocket: WebSocketConfig = field(default_factory=WebSocketConfig)
    sftp: SFTPConfig = field(default_factory=SFTPConfig)
    basicauth: BasicAuthConfig = field(default_factory=BasicAuthConfig)


def load_config_from_env() -> AppConfig:
    config = AppConfig()

    if port := os.getenv("MANAGI_PORT"):
        config.server.port = int(port)
    if host := os.getenv("MANAGI_HOST"):
        config.server.host = host
    if log_level := os.getenv("MANAGI_LOG_LEVEL"):
        config.server.log_level = log_level

    if ssh_timeout := os.getenv("MANAGI_SSH_TIMEOUT"):
        config.ssh.timeout = int(ssh_timeout)
    if keepalive := os.getenv("MANAGI_KEEPALIVE"):
        config.ssh.keepalive_interval = int(keepalive)

    if enabled := os.getenv("MANAGI_BASICAUTH_ENABLED"):
        config.basicauth.enabled = enabled.lower() in ("1", "true", "yes")
    if username := os.getenv("MANAGI_BASICAUTH_USERNAME"):
        config.basicauth.username = username
    if password := os.getenv("MANAGI_BASICAUTH_PASSWORD"):
        config.basicauth.password = password

    return config


config = load_config_from_env()


def get_ssh_config() -> SSHConfig:
    return config.ssh


def get_websocket_config() -> WebSocketConfig:
    return config.websocket


def get_sftp_config() -> SFTPConfig:
    return config.sftp


def get_server_config() -> ServerConfig:
    return config.server


def get_basicauth_config() -> BasicAuthConfig:
    return config.basicauth


async def run_in_executor(func, *args, **kwargs):
    loop = asyncio.get_running_loop()
    partial_func = partial(func, *args, **kwargs)
    return await loop.run_in_executor(None, partial_func)
