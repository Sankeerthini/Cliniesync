#!/usr/bin/env bash
# Optional: run the open-source LLM locally with Ollama (https://ollama.com).
# ClinieSync works without it (deterministic mode); with it you get LLM summaries,
# text-to-SQL fallback, LLM self-check rails in NeMo Guardrails and note translation.
set -euo pipefail
command -v ollama >/dev/null || { echo "Install Ollama first: curl -fsSL https://ollama.com/install.sh | sh"; exit 1; }
ollama pull qwen2.5:7b-instruct      # ~4.7 GB, fits an 8-12 GB GPU
# ollama pull qwen2.5-coder:7b       # optional SQL specialist (set LLM_SQL_MODEL)
echo "Run 'ollama serve' (if not already running), then restart ClinieSync."
