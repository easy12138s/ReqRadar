#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "==> Building frontend..."
cd "$PROJECT_ROOT/frontend"
npm ci
npm run build

echo "==> Verifying static assets..."
STATIC_DIR="$PROJECT_ROOT/src/reqradar/web/static"
if [ ! -f "$STATIC_DIR/index.html" ]; then
  echo "ERROR: Frontend build failed — index.html not found in $STATIC_DIR"
  exit 1
fi
echo "    Static assets: $(find "$STATIC_DIR" -type file | wc -l) files"

echo "==> Building Python package..."
cd "$PROJECT_ROOT"
poetry build

echo "==> Done!"
ls -lh "$PROJECT_ROOT/dist/"
