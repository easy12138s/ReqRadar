FROM python:3.12-slim

WORKDIR /app

COPY reqradar/ reqradar/
COPY services/index/ services/index/

RUN pip install --no-cache-dir --timeout 300 \
    -i https://mirrors.aliyun.com/pypi/simple/ \
    --trusted-host mirrors.aliyun.com \
    fastapi uvicorn httpx sqlalchemy aiosqlite asyncpg pydantic

EXPOSE 8003

CMD ["uvicorn", "services.index.app:app", "--host", "0.0.0.0", "--port", "8003"]
