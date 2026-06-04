# === Stage 1: Frontend build ===
FROM node:22-alpine AS frontend-builder
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --prefer-offline
COPY frontend/ ./
RUN npm run build

# === Stage 2: Python runtime ===
FROM python:3.12-slim AS runtime

WORKDIR /app

RUN addgroup --system appuser && adduser --system --no-create-home --ingroup appuser appuser

RUN apt-get update && \
    apt-get install -y --no-install-recommends git && \
    rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir poetry

COPY pyproject.toml poetry.lock ./
RUN poetry config virtualenvs.create false && \
    poetry install --no-interaction --no-ansi --only main

COPY src/ src/
COPY alembic.ini alembic/ /app/
COPY --from=frontend-builder /frontend/dist/ src/reqradar/web/static/

COPY alembic.ini alembic/ ./
RUN mkdir -p alembic/versions && \
    if [ -d alembic/versions ]; then true; fi

# Pre-download embedding model (respect EMBEDDING_MODEL build arg)
ARG EMBEDDING_MODEL=BAAI/bge-large-zh
ENV EMBEDDING_MODEL=${EMBEDDING_MODEL}
ENV SENTENCE_TRANSFORMERS_HOME=/app/home/models
RUN mkdir -p /app/home/models && \
    python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('${EMBEDDING_MODEL}')" || \
    echo "Warning: Failed to pre-download embedding model. It will be downloaded on first use."

COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

RUN mkdir -p /app/home && chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

ENTRYPOINT ["/entrypoint.sh"]