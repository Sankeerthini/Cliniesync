# ClinieSync on Hugging Face Spaces (Docker, free "CPU basic": 2 vCPU / 16 GB RAM).
# The app and its open-source model (Ollama + qwen2.5:7b-instruct) run together in this one container.
#
# This file is all the Space needs: it pulls the code from GitHub, builds the UI, generates the synthetic
# clinic data, bakes in the model and starts everything. Setup steps: RUNBOOK.md, "Hugging Face".
# While the GitHub repo is private, add a Space secret GITHUB_TOKEN (read-only token for the repo).

ARG REPO=https://github.com/Sankeerthini/Cliniesync.git
ARG GIT_REF=main

# ---- code ---------------------------------------------------------------------------------------
FROM alpine/git:latest AS src
ARG REPO
ARG GIT_REF
RUN --mount=type=secret,id=GITHUB_TOKEN,mode=0444,required=false \
    url="$REPO"; \
    if [ -s /run/secrets/GITHUB_TOKEN ]; then url=$(echo "$REPO" | sed "s#https://#https://x-access-token:$(cat /run/secrets/GITHUB_TOKEN)@#"); fi; \
    git clone --depth 1 --branch "$GIT_REF" "$url" /src && rm -rf /src/.git

# ---- UI -----------------------------------------------------------------------------------------
FROM node:20-bookworm-slim AS ui
COPY --from=src /src/frontend /ui
WORKDIR /ui
RUN npm ci --no-audit --no-fund && npm run build

# ---- app + model ------------------------------------------------------------------------------
FROM python:3.12-slim-bookworm

RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates zstd build-essential \
    && rm -rf /var/lib/apt/lists/* \
    && curl -fsSL https://ollama.com/install.sh | sh

# Spaces run the container as uid 1000
RUN useradd -m -u 1000 user
USER user
RUN mkdir -p /home/user/app
ENV HOME=/home/user PATH=/home/user/venv/bin:$PATH PYTHONUNBUFFERED=1 \
    REFERENCE_DATE=2026-10-19 PORT=7860
WORKDIR /home/user/app

# the model first: ~4.7 GB that rarely changes, so this layer stays cached across code updates
RUN ollama serve >/tmp/ollama.log 2>&1 & \
    until ollama list >/dev/null 2>&1; do sleep 1; done; \
    ollama pull qwen2.5:7b-instruct

COPY --chown=user --from=src /src/requirements.txt .
RUN python -m venv /home/user/venv && pip install --no-cache-dir -r requirements.txt

COPY --chown=user --from=src /src .
COPY --chown=user --from=ui /ui/dist frontend/dist

# synthetic clinic data -> ETL -> SQLite + vector index (same seed as scripts/setup.sh)
RUN python -m data_generator.run --mothers 600 --seed 42 --reference-date "$REFERENCE_DATE" \
    && python -m etl.pipeline

EXPOSE 7860
CMD ["bash", "deploy/huggingface/start.sh"]
