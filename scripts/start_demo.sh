#!/usr/bin/env bash
# One command for the demo: checks the machine, starts ClinieSync, opens a public link and prints it.
#   scripts/start_demo.sh --fixed    app + FIXED public link via Tailscale Funnel (same link every run - use for the hackathon)
#   scripts/start_demo.sh            app + temporary public link (trycloudflare.com, changes every run)
#   scripts/start_demo.sh --local    app only, on http://localhost:8000 (no public link)
# Stop with Ctrl+C - it stops the app (and the Cloudflare tunnel). Logs: data/logs/
set -uo pipefail
cd "$(dirname "$0")/.."
ROOT=$PWD
PORT="${PORT:-8000}"
export REFERENCE_DATE="${REFERENCE_DATE:-2026-10-19}"
MODE=cloudflare
case "${1:-}" in --local) MODE=local ;; --fixed) MODE=fixed ;; "") ;; *) echo "Usage: scripts/start_demo.sh [--fixed | --local]"; exit 2 ;; esac
LOGS="$ROOT/data/logs"; mkdir -p "$LOGS"
APP_PID=""; TUN_PID=""; AWAKE_PID=""

say()  { printf '\033[1;36m==>\033[0m %s\n' "$*"; }
ok()   { printf '\033[1;32m ok\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m  !\033[0m %s\n' "$*"; }
die()  { printf '\033[1;31m  x\033[0m %b\n' "$*"; exit 1; }
envval() { grep -E "^$1=" .env 2>/dev/null | tail -1 | cut -d= -f2- | sed 's/[[:space:]]*#.*$//; s/^"//; s/"$//'; }

cleanup() {
  for p in $APP_PID $TUN_PID $AWAKE_PID; do kill "$p" 2>/dev/null; done
  wait 2>/dev/null
  [ -n "$APP_PID$TUN_PID" ] && { printf '\n'; say "Stopped. Start again with the same command."; }
}
trap cleanup EXIT
trap 'exit 0' INT TERM

say "Checking this machine"

# 1. Python environment (shipped in .venv; rebuilt by scripts/setup.sh if it does not fit this computer)
PY="$ROOT/.venv/bin/python"
if "$PY" -c "import uvicorn, fastapi, chromadb, nemoguardrails" >/dev/null 2>&1; then ok "Python environment"
else die "The Python environment (.venv) is missing or was built for a different kind of computer.
    Rebuild it once (needs Python 3.12, takes a few minutes):  rm -rf .venv && scripts/setup.sh
    Then run:  scripts/start_demo.sh"; fi

# 2. Built UI and data
[ -f frontend/dist/index.html ] && ok "Built UI (frontend/dist)" || die "The built UI (frontend/dist) is missing. Run once:  scripts/setup.sh"
[ -f data/cliniesync.db ] && ok "Database (data/cliniesync.db)" || die "The database is missing. Run once:  scripts/setup.sh"

# 3. Port
if (exec 3<>"/dev/tcp/127.0.0.1/$PORT") 2>/dev/null; then
  die "Port $PORT is already in use - ClinieSync may already be running in another terminal.
    Stop that one with Ctrl+C, or use another port:  PORT=8001 scripts/start_demo.sh"; fi

# 4. Local AI model (optional - without it, answers are record-built and the app still works)
LLM_URL=$(envval LLM_BASE_URL); LLM_URL=${LLM_URL:-http://localhost:11434/v1}
MODEL=$(envval LLM_MODEL); MODEL=${MODEL:-qwen2.5:7b-instruct}
if [ "$(envval LLM_ENABLED)" = "false" ]; then warn "AI model switched off in .env (LLM_ENABLED=false) - record-built answers"
elif TAGS=$("$PY" -c "import urllib.request; print(urllib.request.urlopen('${LLM_URL%/v1}/api/tags', timeout=3).read().decode())" 2>/dev/null); then
  if echo "$TAGS" | grep -q "\"$MODEL\""; then ok "Ollama running with $MODEL"
  else warn "Ollama is running but $MODEL is not downloaded. In another terminal:  ollama pull $MODEL   (then restart this)"; fi
else warn "Ollama is not running - answers will be record-built (the app still works).
    For AI summaries, start it in another terminal:  ollama serve   (or: sudo systemctl start ollama), then restart this."; fi

# 5. E-mail
SMTP_USER=$(envval SMTP_USER)
if [ "$(envval DELIVERY_MODE)" = "sandbox" ]; then warn "E-mail in sandbox mode (nothing is sent) - see .env DELIVERY_MODE"
elif [ -n "$SMTP_USER" ] && [ -n "$(envval SMTP_PASSWORD)" ]; then ok "E-mail sends from $SMTP_USER"
else warn "E-mail not set up - Share report by e-mail will not send. Set it up with:  .venv/bin/python scripts/setup_email.py"; fi

# 6. Public link
if [ $MODE = fixed ]; then
  # Tailscale Funnel: the link belongs to this computer, so it is the same on every run (one-time setup: RUNBOOK.md)
  command -v tailscale >/dev/null 2>&1 || die "Tailscale is not installed - see \"Fixed link (one-time setup)\" in RUNBOOK.md.
    Or use a temporary link instead:  scripts/start_demo.sh"
  TS_JSON=$(tailscale status --json 2>/dev/null) || die "Tailscale is not running or not signed in. Run:  sudo tailscale up   (then run this again)"
  HOST=$(printf '%s' "$TS_JSON" | "$PY" -c "import sys, json; d = json.load(sys.stdin); print(d.get('Self', {}).get('DNSName', '').rstrip('.') if d.get('BackendState') == 'Running' else '')" 2>/dev/null)
  [ -n "$HOST" ] || die "Tailscale is not signed in. Run:  sudo tailscale up   (then run this again)"
  say "Checking the fixed link (Tailscale Funnel)"
  funnel_on() { local st; st=$(tailscale funnel status 2>/dev/null); echo "$st" | grep -q "Funnel on" && echo "$st" | grep -qE "(127\.0\.0\.1|localhost):$PORT"; }
  if ! funnel_on; then
    # first run on this computer (or another port): point the funnel at the app; it is remembered across restarts
    FOUT=$( if command -v timeout >/dev/null; then timeout 25 tailscale funnel --bg "$PORT"; else tailscale funnel --bg "$PORT"; fi </dev/null 2>&1 )
    funnel_on || die "Could not switch the fixed link on. Tailscale said:\n$FOUT\n
    If it shows a login.tailscale.com link: open it, allow Funnel, then run this again.
    If it says \"access denied\": run once  sudo tailscale set --operator=\$USER   and run this again."
  fi
  ok "Fixed public link: https://$HOST"
  export PUBLIC_BASE_URL="https://$HOST"     # links inside shared reports point here (overrides .env)
elif [ $MODE = cloudflare ]; then
  command -v cloudflared >/dev/null 2>&1 || die "cloudflared (the tunnel tool) is not installed.
    Ubuntu/Debian:  sudo apt install $ROOT/cloudflared-linux-amd64.deb
    Other systems:  https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/
    For the fixed hackathon link use:  scripts/start_demo.sh --fixed   ·   no public link:  scripts/start_demo.sh --local"
  say "Opening a temporary public link (Cloudflare quick tunnel)"
  cloudflared tunnel --no-autoupdate --url "http://127.0.0.1:$PORT" >"$LOGS/tunnel.log" 2>&1 &
  TUN_PID=$!
  URL=""
  for _ in $(seq 1 60); do
    URL=$(grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' "$LOGS/tunnel.log" | head -1)
    [ -n "$URL" ] && break
    kill -0 "$TUN_PID" 2>/dev/null || die "The tunnel stopped. Last lines of data/logs/tunnel.log:\n$(tail -5 "$LOGS/tunnel.log")"
    sleep 1
  done
  [ -n "$URL" ] || die "No public link after 60 seconds - check the internet connection. Details: data/logs/tunnel.log"
  ok "Temporary public link: $URL"
  export PUBLIC_BASE_URL="$URL"
else
  export PUBLIC_BASE_URL=""         # report links use the address in the doctor's browser
fi

# 7. App
say "Starting ClinieSync (first start takes ~20-40 s while the safety rails load)"
"$PY" -m uvicorn backend.app.main:app --host 127.0.0.1 --port "$PORT" >"$LOGS/app.log" 2>&1 &
APP_PID=$!
for i in $(seq 1 180); do
  "$PY" -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:$PORT/api/auth/demo-users', timeout=2)" >/dev/null 2>&1 && break
  kill -0 "$APP_PID" 2>/dev/null || die "ClinieSync did not start. Last lines of data/logs/app.log:\n$(tail -15 "$LOGS/app.log")"
  [ "$i" = 180 ] && die "ClinieSync is taking too long to start. Details: data/logs/app.log"
  sleep 1
done

# 8. Keep the computer awake while the demo runs
if command -v systemd-inhibit >/dev/null 2>&1; then
  systemd-inhibit --what=idle:sleep --who=ClinieSync --why="Demo is running" sleep infinity >/dev/null 2>&1 & AWAKE_PID=$!
elif command -v caffeinate >/dev/null 2>&1; then caffeinate -dims -w "$APP_PID" >/dev/null 2>&1 & AWAKE_PID=$!; fi

LINK=${PUBLIC_BASE_URL:-http://localhost:$PORT}
printf '\n\033[1;32m  ClinieSync is live\033[0m\n\n'
printf '  Link to share:   \033[1m%s\033[0m\n' "$LINK"
printf '  On this machine: http://localhost:%s\n\n' "$PORT"
printf '  Sign in with a role card (password: demo123):\n    Dr. Ananya Rao (doctor) · Rekha S. (care coordinator) · Hospital Administrator\n\n'
printf '  Keep this terminal open and the computer plugged in. Ctrl+C stops everything.\n'
[ $MODE = cloudflare ] && printf '  This link changes every time this script restarts - for a fixed link use --fixed.\n'
[ $MODE = fixed ] && printf '  This link stays the same - after a restart or reboot just run this command again.\n'
printf '\n'

# 9. Watch both processes; say clearly which one stopped
while kill -0 "$APP_PID" 2>/dev/null; do
  if [ -n "$TUN_PID" ] && ! kill -0 "$TUN_PID" 2>/dev/null; then
    warn "The tunnel stopped (internet drop?). The public link no longer works - press Ctrl+C and run this again."; TUN_PID=""; fi
  sleep 3
done
warn "ClinieSync stopped unexpectedly. Last lines of data/logs/app.log:"; tail -15 "$LOGS/app.log"
