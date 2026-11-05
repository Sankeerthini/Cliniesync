#!/usr/bin/env bash
# One-time setup of a Google Cloud VM (Ubuntu 24.04) for the ClinieSync demo. From the unzipped app folder:
#   bash deploy/gcp/setup_server.sh
# Installs the model (Ollama + qwen2.5:7b-instruct) and the Python environment, then two services that start on
# boot and restart on failure: the app (systemd) and Caddy, which serves it over HTTPS at https://<ip>.sslip.io.
# Safe to run again (e.g. after uploading a newer copy of the app).
set -euo pipefail
cd "$(dirname "$0")/../.."
APP=$PWD
ME=$(id -un)
MODEL=qwen2.5:7b-instruct
say() { printf '\n\033[1;36m==>\033[0m %s\n' "$*"; }
die() { printf '\033[1;31m  x\033[0m %s\n' "$*"; exit 1; }

[ -f frontend/dist/index.html ] && [ -f data/cliniesync.db ] || die "Run this from the unzipped ClinieSync folder (frontend/dist and data/ missing)."

say "System packages"
sudo apt-get update -qq
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq curl unzip tmux caddy >/dev/null

say "Ollama + $MODEL (4.7 GB download, a few minutes)"
command -v ollama >/dev/null || curl -fsSL https://ollama.com/install.sh | sh
# keep the model in memory between questions (Ollama unloads it after 5 idle minutes by default)
sudo mkdir -p /etc/systemd/system/ollama.service.d
printf '[Service]\nEnvironment="OLLAMA_KEEP_ALIVE=-1"\n' | sudo tee /etc/systemd/system/ollama.service.d/keep-alive.conf >/dev/null
sudo systemctl daemon-reload
sudo systemctl enable --now ollama >/dev/null 2>&1
sudo systemctl restart ollama
until ollama list >/dev/null 2>&1; do sleep 1; done
ollama pull "$MODEL"

say "Python environment"
export PATH="$HOME/.local/bin:$PATH"
if .venv/bin/python -c "import uvicorn, fastapi, chromadb, nemoguardrails" 2>/dev/null; then echo "already set up"
else
  command -v uv >/dev/null || curl -LsSf https://astral.sh/uv/install.sh | sh
  rm -rf .venv
  uv venv .venv --python 3.12 -q
  uv pip install --python .venv/bin/python -q -r requirements.txt
fi

say "Public address"
IP=$(curl -fs -H "Metadata-Flavor: Google" \
  http://metadata.google.internal/computeMetadata/v1/instance/network-interfaces/0/access-configs/0/external-ip) \
  || die "This VM has no external IP - edit the VM and give it one (Networking -> External IPv4 address)."
HOST="${IP//./-}.sslip.io"     # sslip.io resolves 34-93-1-2.sslip.io to 34.93.1.2, so Caddy can get a certificate
echo "$HOST"

say "App service (starts on boot, restarts if it stops)"
sudo tee /etc/systemd/system/cliniesync.service >/dev/null <<EOF
[Unit]
Description=ClinieSync demo
After=network-online.target ollama.service
Wants=network-online.target ollama.service

[Service]
User=$ME
WorkingDirectory=$APP
Environment=REFERENCE_DATE=2026-10-19
Environment=PUBLIC_BASE_URL=https://$HOST
ExecStart=$APP/.venv/bin/python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --proxy-headers
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
sudo systemctl daemon-reload
sudo systemctl enable cliniesync >/dev/null 2>&1
sudo systemctl restart cliniesync

say "HTTPS (Caddy)"
sudo tee /etc/caddy/Caddyfile >/dev/null <<EOF
$HOST {
	encode gzip
	reverse_proxy 127.0.0.1:8000
}
EOF
sudo systemctl enable caddy >/dev/null 2>&1
sudo systemctl restart caddy

say "Waiting for the app (first start takes ~30 s)"
for i in $(seq 1 180); do
  curl -fs -o /dev/null http://127.0.0.1:8000/api/auth/demo-users && break
  [ "$i" = 180 ] && die "The app did not start. See:  journalctl -u cliniesync -n 40"
  sleep 1
done
for i in $(seq 1 90); do
  curl -fs -o /dev/null "https://$HOST/api/auth/demo-users" && break
  [ "$i" = 90 ] && die "The app runs, but https://$HOST does not answer. Check the VM allows HTTP and HTTPS traffic
    (VM -> Edit -> Firewalls: tick both), then:  sudo systemctl restart caddy"
  sleep 2
done

printf '\n\033[1;32m  ClinieSync is live\033[0m\n\n  Link to share:   \033[1mhttps://%s\033[0m\n\n' "$HOST"
printf '  Sign in with a role card (password: demo123).\n'
printf '  It keeps running after you close this window and comes back by itself after a reboot.\n\n'
