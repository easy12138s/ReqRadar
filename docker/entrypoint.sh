#!/usr/bin/env bash
set -euo pipefail

if [ ! -f /app/.reqradar.yaml ]; then
    cat > /app/.reqradar.yaml <<EOF
web:
  host: "0.0.0.0"
  port: 8000
  secret_key: "${REQRADAR_SECRET_KEY:-change-me-in-production}"
  database_url: "sqlite+aiosqlite:////app/data/reqradar.db"
  auto_create_tables: false
index:
  embedding_model: "BAAI/bge-large-zh"
  storage_path: "/app/.reqradar/index"
memory:
  storage_path: "/app/.reqradar/memory"
llm:
  provider: "${LLM_PROVIDER:-openai}"
  model: "${LLM_MODEL:-gpt-4o-mini}"
  api_key: "${OPENAI_API_KEY:-}"
  base_url: "${OPENAI_BASE_URL:-}"
EOF
fi

echo "Running database migrations..."
alembic upgrade head || echo "Warning: migration failed, continuing..."

exec reqradar serve --host 0.0.0.0 --port 8000
