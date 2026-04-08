# Managi Backend

轻量级网页版 SSH 管理工具后端服务

## 技术栈

| 技术 | 版本 |
|------|------|
| FastAPI | 0.115.6 |
| Uvicorn | 0.34.0 |
| Paramiko | 3.5.0 |
| Pydantic | 2.12.5 |

## 项目结构

```
managi-backend-python/
├── app.py              # FastAPI 应用入口
├── routers.py          # API 路由 (SSH/SFTP WebSocket)
├── models.py           # Pydantic 数据模型
├── setting.py          # 配置管理 (支持环境变量)
├── common.py           # 通用工具
├── ssh_pool.py         # SSH 连接池
├── sftp_client.py      # SFTP 客户端
├── index.html          # 前端页面 (打包时嵌入)
└── requirements.txt    # Python 依赖
```

## 核心功能

### 1. 批量命令执行
- **单节点**: `POST /api/ssh/test`
- **批量**: `POST /api/ssh/batch` (并发执行)

### 2. Web SSH 终端
- **WebSocket**: `/ws`
- 支持终端尺寸动态调整
- 心跳保活机制

### 3. SFTP 文件管理
- **WebSocket**: `/ws/sftp`
- 支持操作: list, upload, download, mkdir, delete, rename
- 进度实时推送

## 配置说明

### 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `MANAGI_PORT` | 18001 | 服务端口 |
| `MANAGI_HOST` | 0.0.0.0 | 绑定地址 |
| `MANAGI_LOG_LEVEL` | error | 日志级别 |
| `MANAGI_SSH_TIMEOUT` | 15 | SSH 超时秒数 |
| `MANAGI_KEEPALIVE` | 30 | 心跳间隔秒数 |

### 配置文件 (setting.py)

```python
@dataclass
class SSHConfig:
    timeout: int = 15              # SSH 连接超时
    banner_timeout: int = 15       # SSH 横幅超时
    keepalive_interval: int = 30   # Keepalive 间隔

@dataclass
class WebSocketConfig:
    heartbeat_interval: int = 10000  # 心跳间隔 (ms)
    heartbeat_timeout: int = 10000    # 心跳超时 (ms)
    max_buffer_size: int = 4096        # 最大缓冲区

@dataclass
class SFTPConfig:
    chunk_size: int = 32768          # 分块大小
    download_chunk_size: int = 65536  # 下载分块
```

## 快速开始

### 安装依赖

```bash
pip install -r requirements.txt
```

### 启动服务

```bash
# 默认端口 18001
python app.py

# 指定端口
python app.py -p 8080

# 指定地址和端口
python app.py --host 127.0.0.1 --port 8080
```

### Docker 部署

```bash
# 构建镜像
docker build -t managi:latest .

# 运行容器
docker run -d --network host managi:latest
```

## API 接口

### 命令执行

```bash
# 单节点测试
curl -X POST http://localhost:18001/api/ssh/test \
  -H "Content-Type: application/json" \
  -d '{
    "node": {
      "name": "server1",
      "host": "192.168.1.100",
      "port": 22,
      "username": "root",
      "auth_type": "password",
      "auth_value": "password"
    },
    "cmds": ["uname -a", "df -h"]
  }'
```

### WebSocket 连接

```javascript
// SSH 终端
const ws = new WebSocket('ws://localhost:18001/ws');
ws.onopen = () => ws.send(JSON.stringify(node));

// SFTP 文件管理
const ws = new WebSocket('ws://localhost:18001/ws/sftp');
```

## 设计原则

- **模块化**: 职责分离，每个文件专注单一功能
- **配置中心化**: 统一管理配置，支持环境变量覆盖
- **连接池复用**: SSH 连接池减少重复连接开销
- **异步化**: 尽可能使用异步处理，提升并发能力

## 许可证

MIT License
