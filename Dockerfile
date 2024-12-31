# 使用 Python 3.9 的 Alpine 镜像
FROM python:3.9-alpine

# 安装 git 和其他必要的依赖
RUN apk add --no-cache git

# 设置工作目录
WORKDIR /app

# 从 GitHub 拉取代码
RUN git clone https://github.com/hochenggang/managi-backend.git .

# 安装依赖
RUN pip install --no-cache-dir -r requirements.txt

# 暴露端口
EXPOSE 18001

# 启动应用
CMD ["python3", "app.py", "-p", "18001"]