FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py .

# 使用 sh -c 来执行启动命令，这样就可以动态读取 .env 注入的 SERVER_PORT 环境变量
# 如果找不到环境变量，则默认回退到监听 8000 端口
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${SERVER_PORT:-8000}"]
