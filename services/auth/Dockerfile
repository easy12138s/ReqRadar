FROM python:3.12-slim

WORKDIR /app

COPY reqradar/ reqradar/
COPY services/auth/ services/auth/

RUN pip install --no-cache-dir --break-system-packages fastapi uvicorn pyjwt sqlalchemy aiosqlite asyncpg pydantic

EXPOSE 8001

CMD ["uvicorn", "services.auth.app:app", "--host", "0.0.0.0", "--port", "8001"]
