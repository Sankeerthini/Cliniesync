#!/usr/bin/env bash
# One-time setup: Python env, synthetic data, ETL, frontend build.
set -euo pipefail
cd "$(dirname "$0")/.."
export REFERENCE_DATE="${REFERENCE_DATE:-2026-10-19}"

echo "==> Python environment"
if command -v uv >/dev/null; then uv venv .venv --python 3.12 -q && uv pip install --python .venv/bin/python -q -r requirements.txt
else python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt; fi

echo "==> Synthetic clinic data (EHR exports, Excel register, PDF reports, notes)"
.venv/bin/python -m data_generator.run --mothers 600 --seed 42 --reference-date "$REFERENCE_DATE"

echo "==> ETL: extract -> clean -> normalise -> link -> load -> index"
.venv/bin/python -m etl.pipeline

echo "==> Tests"
.venv/bin/python -m pytest -q

echo "==> Frontend (needs Node.js 18+)"
if command -v npm >/dev/null; then (cd frontend && npm install --no-audit --no-fund && npm run build)
else echo "   npm not found - install Node.js to build the UI (backend API still works)"; fi
echo "Done. Start with: scripts/run.sh"
