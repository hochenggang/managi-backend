from typing import List
import uuid
import time
import sqlite3
import threading
import hashlib
from collections import OrderedDict
import json
import io

from fastapi import FastAPI, Depends, HTTPException, Header, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import paramiko


# FastAPI 应用
app = FastAPI()


class Token:
    '''
    简易的验证类，用于验证令牌
    '''
    def __init__(self):
        self.tokens = OrderedDict()
        self.lock_token_operation = threading.Lock()

    def add_token(self, token_id: str, token_info: dict):
        with self.lock_token_operation:  # 确保线程安全
            if token_id in self.tokens:
                # 如果 token_id 已经存在，更新其信息并将其移动到末尾
                self.tokens.move_to_end(token_id)
                self.tokens[token_id] = token_info
            else:
                # 如果 tokens 的长度大于 100，则删除最旧的 token
                if len(self.tokens) >= 100:
                    self.tokens.popitem(last=False)  # 移除最旧的项
                self.tokens[token_id] = token_info
                self.tokens.move_to_end(token_id, last=False)  # 将新插入的 token_id 移动到最前面

    def generate_token(self, user_name):
        token = str(uuid.uuid4())
        create_at = round(time.time())
        expire_at = create_at + 3600
        self.add_token(token, {"user_name": user_name, "create_at":create_at, "expire_at": expire_at})
        return token

    def verify_token(self, authorization: str = Header(None))->dict:
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Invalid Authorization header")
        token = authorization.split(" ")[1]
        with self.lock_token_operation:  # 确保线程安全
            if token not in self.tokens:
                raise HTTPException(status_code=401, detail="Invalid or expired token")
            token_info = self.tokens[token]
            if time.time() > token_info["expire_at"]:
                del self.tokens[token]  # 删除过期的 token
                raise HTTPException(status_code=401, detail="Invalid or expired token")
            return token_info


# 验证类实例
token_manager = Token()


# 数据库连接管理类
class DatabaseConnection:
    def __init__(self, db_path):
        self.db_path = db_path
        self.lock = threading.Lock()

    def execute_query(self, query, params=None, fetch=False):
        """
        执行 SQL 查询，并在操作完成后立即释放连接。
        :param query: SQL 查询语句
        :param params: 查询参数
        :param fetch: 是否获取查询结果
        :return: 如果 fetch=True，返回查询结果；否则返回 None
        """
        if not self.lock.acquire(timeout=5):  # 设置超时时间为 5 秒
            raise TimeoutError("获取数据库连接超时")
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            if fetch:
                result = cursor.fetchall()
            else:
                result = None
            conn.commit()
            return result
        finally:
            if conn:
                conn.close()
            self.lock.release()


# 数据库连接实例
db = DatabaseConnection("management.db")

# 初始化数据库
def init_db():
    db.execute_query('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL
        )
    ''')


# 初始化数据库
init_db()

# 数据模型
class User(BaseModel):
    username: str
    password: str

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
    
class TokenInfoResult(BaseModel):
    username: str
    create_at: str
    expire_at: str

# SSH 连接类
class SSHConnection:
    def __init__(self, ip:str, port:int, ssh_username:str, auth_type:str, auth_value:str):
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
            self.ssh.connect(self.ip, port=self.port, username=self.ssh_username, password=self.auth_value, timeout=5)
        elif self.auth_type == "key":
            # 使用密钥认证
            key = paramiko.RSAKey.from_private_key_file(io.StringIO(self.auth_value))
            self.ssh.connect(self.ip, port=self.port, username=self.ssh_username, pkey=key, timeout=5)
        else:
            raise ValueError(f"Unsupported auth_type: {self.auth_type}")
        return self.ssh

    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        关闭 SSH 连接。
        """
        if self.ssh:
            self.ssh.close()


# 缓存管理员的数量，用于防止管理员初始化接口被call多次
cache_admin_user_count = db.execute_query("SELECT COUNT(*) FROM users", fetch=True)[0][0]
# API 端点
@app.post("/api/admin/init")
def create_admin(user: User):
    '''
    为第一次访问的人创建管理员账号，初始化数据库，并返回成功信息。
    :param user: 用户名、密码
    :return: 成功信息
    '''
    global cache_admin_user_count
    if cache_admin_user_count > 0:
        return Response(status_code=403, content="Admin already exists")
    else:
        # 对用户名和密码进行检测
        if not all([len(user.username)>=3, len(user.password)>=6]):
            return Response(status_code=400, content="用户名或者密码太短")
        
        password_hash = hashlib.sha256(user.password.encode()).hexdigest()
        db.execute_query("INSERT INTO users (username, password_hash) VALUES (?, ?)",
                        (user.username, password_hash))
        cache_admin_user_count += 1
        return Response(status_code=200, content="Success")

@app.post("/api/login")
def login(user: User):
    '''
    实现用户登录接口，返回token
    '''
    # 这个接口后续需要进行限流，1小时允许3次
    password_hash = hashlib.sha256(user.password.encode()).hexdigest()
    result = db.execute_query("SELECT username FROM users WHERE username = ? AND password_hash = ?",
                              (user.username, password_hash), fetch=True)
    if not result:
        return JSONResponse(status_code=401, content={
            "error": "Unauthorized",
            "message": "Invalid username or password"
            })
    username = result[0][0]
    token = token_manager.generate_token(username)
    return {"access_token": token, "token_type": "bearer"}


@app.get("/api/token/info")
def get_api_token_info(token: dict = Depends(token_manager.verify_token))->TokenInfoResult:
    '''
    返回token的有效期和用户名
    '''
    print(token)
    return Response(status_code=200, content=json.dumps(token))


@app.post("/api/ssh/test")
def test_ssh_connection(node: Node,cmds: List[str], token: dict = Depends(token_manager.verify_token))->CmdsTestResult:
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
        with SSHConnection(node.ip, node.port, node.ssh_username, node.auth_type, node.auth_value) as ssh:
            # 执行测试命令
            stdin, stdout, stderr = ssh.exec_command(commands)
            output = stdout.readlines()
            error = stderr.readlines()
            success = True
    except Exception as e:
        success = False
        output = ['']
        error = [str(e)]
    end_time = time.time()

    # 返回连接耗时、连接是否成功、测试命令输出和错误信息
    return {
        "time_elapsed": round(end_time - start_time, 2),  # 连接耗时，保留两位小数
        "success": success,
        "output": output,
        "error": error,
        "node":{
            "name":node.name,
            "ip":node.ip,
            "ssh_username":node.ssh_username,
            "port":node.port,
            "auth_type":node.auth_type,
            "auth_value":'***',
        },
        "cmds":commands
    }


@app.get("/api/ping")
def get_ping():
    '''
    测试接口是否正常
    返回初始化状态
    '''
    global cache_admin_user_count
    cache_api_ping = {}
    cache_api_ping['pong'] = cache_admin_user_count
    return cache_api_ping

# OPTION /*
@app.options("/{path:path}")
async def options_handler(path: str):
    '''
    跨域请求处理
    '''
    return Response(status_code=204)

# 添加 CORS 头
@app.middleware("http")
async def add_cors_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type,Authorization'
    response.headers['Access-Control-Allow-Methods'] = 'GET,PUT,POST,DELETE,OPTIONS'
    response.headers['X-VERSION'] = "20241230"
    return response


# 启动应用
if __name__ == "__main__":
    import argparse
    import uvicorn
    parser = argparse.ArgumentParser(description="Run the FastAPI application.")
    parser.add_argument("-p", "--port", type=int, default=18001, help="Port to run the application on.")
    
    # 解析命令行参数
    args = parser.parse_args()
    uvicorn.run(app, host="0.0.0.0", port=args.port)

