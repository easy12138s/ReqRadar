FROM python:3.12-slim

WORKDIR /app

COPY reqradar/kernel/ reqradar/kernel/
COPY reqradar/infrastructure/ reqradar/infrastructure/
COPY services/auth/ services/auth/

RUN pip install --no-cache-dir fastapi uvicorn pyjwt sqlalchemy aiosqlite

EXPOSE 8001

CMD ["uvicorn", "services.auth.app:app", "--host", "0.0.0.0", "--port", "8001"]
