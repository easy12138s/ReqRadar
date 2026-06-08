FROM python:3.12-slim

WORKDIR /app

COPY reqradar/kernel/ reqradar/kernel/
COPY reqradar/index_svc/ reqradar/index_svc/
COPY reqradar/infrastructure/ reqradar/infrastructure/
COPY services/integration/ services/integration/

RUN pip install --no-cache-dir --break-system-packages -i https://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com fastapi uvicorn httpx fastmcp sqlalchemy aiosqlite

EXPOSE 8005

CMD ["uvicorn", "services.integration.app:app", "--host", "0.0.0.0", "--port", "8005"]
