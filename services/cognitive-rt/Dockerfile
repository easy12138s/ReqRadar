FROM python:3.12-slim

WORKDIR /app

COPY reqradar/ reqradar/

RUN pip install --no-cache-dir --break-system-packages fastapi uvicorn httpx pyjwt sqlalchemy aiosqlite asyncpg psycopg2-binary redis pydantic pyyaml

EXPOSE 8002

CMD ["uvicorn", "reqradar.cognitive_rt.runtime.server:app", "--host", "0.0.0.0", "--port", "8002"]
