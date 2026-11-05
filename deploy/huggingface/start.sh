#!/usr/bin/env bash
# Container entry point on Hugging Face Spaces: start the model server, tune it to this CPU, load the model, start the app.
set -uo pipefail
cd "$(dirname "$0")/../.."
MODEL="${LLM_MODEL:-qwen2.5:7b-instruct}"

# CPUs this container may really use. nproc reports the whole host, and llama.cpp running one thread per host
# core inside a 2-CPU quota spends most of its time throttled - pinning the count is the biggest CPU speed-up.
cpus=$(nproc)
if [ -r /sys/fs/cgroup/cpu.max ]; then
  read -r quota period < /sys/fs/cgroup/cpu.max
  [ "$quota" != max ] && cpus=$(( (quota + period - 1) / period ))
fi
echo "==> $cpus CPU(s) available"

# one request at a time gets the whole CPU (parallel slots would only split it); keep the model in memory for good
export OLLAMA_NUM_PARALLEL=1 OLLAMA_MAX_LOADED_MODELS=1 OLLAMA_KEEP_ALIVE=-1
ollama serve >/tmp/ollama.log 2>&1 &
until ollama list >/dev/null 2>&1; do sleep 1; done

# same weights, thread count set for this machine (only the runtime parameter changes)
printf 'FROM %s\nPARAMETER num_thread %s\n' "$MODEL" "$cpus" >/tmp/Modelfile
ollama create "$MODEL" -f /tmp/Modelfile >/dev/null 2>&1 && echo "==> $MODEL set to $cpus thread(s)" \
  || echo "==> could not set the thread count - using Ollama's default"

# load it now, so the first visitor does not wait for 4.7 GB to come off disk
echo "==> Loading $MODEL"
curl -s -m 600 http://127.0.0.1:11434/api/generate -d "{\"model\": \"$MODEL\", \"keep_alive\": -1}" >/dev/null \
  && echo "==> Model loaded" || echo "==> Model did not load - answers will be record-built until it does"

# CPU-only server: allow slow answers (the UI polls, so nothing times out in the browser) and skip the two extra
# LLM self-check calls per question; the deterministic NeMo rails still check every question and answer.
export LLM_TIMEOUT_S="${LLM_TIMEOUT_S:-300}" LLM_SELF_CHECK="${LLM_SELF_CHECK:-false}"
[ -n "${SPACE_HOST:-}" ] && export PUBLIC_BASE_URL="${PUBLIC_BASE_URL:-https://$SPACE_HOST}"

exec python -m uvicorn backend.app.main:app --host 0.0.0.0 --port "${PORT:-7860}" --proxy-headers --forwarded-allow-ips='*'
