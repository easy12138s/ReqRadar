FROM python:3.12-slim

WORKDIR /app

COPY reqradar/kernel/ reqradar/kernel/
COPY reqradar/infrastructure/ reqradar/infrastructure/
COPY services/api/ services/api/

RUN pip install --no-cache-dir fastapi uvicorn httpx pyjwt sqlalchemy aiosqlite

EXPOSE 8000

CMD ["uvicorn", "services.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
