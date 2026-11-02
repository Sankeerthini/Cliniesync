#!/usr/bin/env bash
# Start ClinieSync (API + built UI on http://localhost:8000).  For UI hot-reload: cd frontend && npm run dev
set -euo pipefail
cd "$(dirname "$0")/.."
export REFERENCE_DATE="${REFERENCE_DATE:-2026-10-19}"
exec .venv/bin/uvicorn backend.app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
