#!/usr/bin/env bash
set -euo pipefail

# ── Load .env if present ──
if [ -f /app/.env ]; then
  set -a
  while IFS='=' read -r key value; do
    key=$(echo "$key" | xargs)
    value=$(echo "$value" | xargs)
    if [ -n "$key" ] && [[ ! "$key" =~ ^# ]]; then
      export "$key=$value"
    fi
  done < /app/.env
  set +a
  echo "Loaded .env file"
fi

REQRADAR_HOME="${REQRADAR_HOME:-/app/home}"
export REQRADAR_HOME

# ── Ensure home directories exist ──
mkdir -p "${REQRADAR_HOME}"/{projects,memories,reports,models,db}

# ── Generate configuration if not present ──
if [ ! -f /app/.reqradar.yaml ]; then
  cat > /app/.reqradar.yaml <<EOF
home:
  path: "${REQRADAR_HOME}"

llm:
  provider: "${LLM_PROVIDER:-openai}"
  model: "${LLM_MODEL:-gpt-4o-mini}"
  api_key: "${OPENAI_API_KEY:-}"
  base_url: "${OPENAI_BASE_URL:-https://api.openai.com/v1}"
  timeout: 60
  max_retries: 2

vision:
  provider: "${LLM_PROVIDER:-openai}"
  model: "gpt-4o"
  api_key: "${OPENAI_API_KEY:-}"
  base_url: "${OPENAI_BASE_URL:-https://api.openai.com/v1}"
  timeout: 120
  max_retries: 2

memory:
  enabled: true
  storage_path: ""

loader:
  chunk_size: 300
  chunk_overlap: 50

index:
  embedding_model: "${EMBEDDING_MODEL:-BAAI/bge-large-zh}"
  chunk_size: 300
  chunk_overlap: 50
  storage_path: ""
  model_cache: "${REQRADAR_HOME}/models"

analysis:
  max_similar_reqs: 5
  max_code_files: 10
  contributors_lookback_months: 6

git:
  lookback_months: 6

output:
  report_template: default
  format: markdown

log:
  level: "${REQRADAR_LOG_LEVEL:-INFO}"
  format: console

agent:
  mode: react
  max_steps_quick: 10
  max_steps_standard: 15
  max_steps_deep: 25
  version_limit: 10

web:
  host: "0.0.0.0"
  port: 8000
  database_url: "sqlite+aiosqlite:////${REQRADAR_HOME}/db/reqradar.db"
  reports_path: "${REQRADAR_HOME}/reports"
  secret_key: "${REQRADAR_SECRET_KEY:-change-me-in-production}"
  access_token_expire_minutes: 1440
  max_concurrent_analyses: 2
  max_upload_size: 50
  cors_origins: ""
  debug: false
  auto_create_tables: false
  allowed_upload_extensions: ".txt,.md,.pdf,.docx,.xlsx,.csv,.json,.yaml,.yml,.html,.png,.jpg,.jpeg,.gif,.bmp"
  db_pool_size: 5
  db_pool_max_overflow: 10
  data_root: "${REQRADAR_HOME}/projects"

reporting:
  default_template_id: 1
EOF
  echo "Generated .reqradar.yaml configuration"
fi

# ── Validate critical settings ──
if [ "${REQRADAR_SECRET_KEY:-}" = "change-me-in-production" ] || [ "${REQRADAR_SECRET_KEY:-}" = "" ]; then
  echo "WARNING: Using default SECRET_KEY. Set REQRADAR_SECRET_KEY environment variable for production!"
fi

if [ "${OPENAI_API_KEY:-}" = "" ]; then
  echo "WARNING: OPENAI_API_KEY is not set. LLM features will not work until configured."
fi

# ── Run database migrations ──
echo "Running database migrations..."
cd /app
alembic upgrade head || {
  echo "WARNING: Database migration failed. Tables will be auto-created if needed."
}

# ── Start server ──
echo "Starting ReqRadar server..."
exec reqradar serve --host 0.0.0.0 --port 8000
