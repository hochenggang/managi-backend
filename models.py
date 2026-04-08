from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


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

    def get_connection_key(self) -> str:
        return f"{self.host}:{self.port}:{self.username}"


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
    new_path: Optional[str] = Field(None, description="New path for rename/move operations")
    content: Optional[str] = Field(None, description="Optional content for file creation")


class FileOperationResponse(BaseModel):
    success: bool = Field(..., description="Whether the operation succeeded")
    message: str = Field(..., description="Result message")
    path: Optional[str] = Field(None, description="Affected file/directory path")
    size: Optional[int] = Field(None, description="File size in bytes")
    files: Optional[List[FileItem]] = Field(None, description="Directory listing")
    complete: Optional[bool] = Field(None, description="For downloads, indicates completion")


class DownloadMetadata(BaseModel):
    success: bool = Field(..., description="Whether download can proceed")
    filename: Optional[str] = Field(None, description="Name of the file to download")
    size: Optional[int] = Field(None, description="Size of the file in bytes")
    message: Optional[str] = Field(None, description="Error message if success=False")


class BatchCmdRequest(BaseModel):
    nodes: List[Node] = Field(..., description="List of nodes to execute commands on")
    cmds: List[str] = Field(..., description="Commands to execute")
