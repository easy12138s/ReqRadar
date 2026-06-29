FROM python:3.12-slim

WORKDIR /app

COPY reqradar/ reqradar/
COPY services/api/ services/api/

RUN pip install --no-cache-dir --break-system-packages fastapi uvicorn httpx pyjwt sqlalchemy aiosqlite asyncpg redis pydantic python-multipart

EXPOSE 8000

CMD ["uvicorn", "services.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
