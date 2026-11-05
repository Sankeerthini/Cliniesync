# Running the ClinieSync demo

Two ways to give people a link: a Google Cloud server that runs on its own, or your own machine with a tunnel.
Both keep the same link every time.

## Public link on a Google Cloud server (no one's computer needs to stay on)

A small Ubuntu server on Google Cloud runs the same app and model (Ollama + qwen2.5:7b-instruct) around the clock.
The free trial ($300 credit, 90 days) covers it; nothing is charged unless the account is upgraded to paid.

1. **Create the server** - console.cloud.google.com → Compute Engine → VM instances → **Create instance**:
   region `asia-south1` (Mumbai), machine type `e2-standard-8`, boot disk **Ubuntu 24.04 LTS (x86/64)**, 50 GB;
   Networking: tick **Allow HTTP traffic** and **Allow HTTPS traffic**, and set the external IPv4 address to a
   **static** one (so the link never changes).
2. **Upload the app** - click **SSH** next to the server → in that window **Upload file** → the app zip
   (`ClinieSync_server.zip`: this repo plus the built UI, the data and `.env`).
3. **Install and start** - in the SSH window:
   ```bash
   unzip -q ClinieSync_server.zip && cd cliniesync
   bash deploy/gcp/setup_server.sh
   ```
   About 10 minutes. It ends with the link: `https://<ip-with-dashes>.sslip.io`.

The app and the model start on boot and restart if they stop - nobody has to keep a terminal open.

- Status / logs: `systemctl status cliniesync` · `journalctl -u cliniesync -n 50`
- Restart: `sudo systemctl restart cliniesync`
- Update the app: upload the new zip, `unzip -oq ClinieSync_server.zip`, run the setup script again.
- Credit: e2-standard-8 uses about $7-8 of credit a day (~40 days); `e2-standard-4` halves that, with slower AI answers
  (VM → Stop → Edit → Machine type). A stopped VM uses almost no credit.

## Running it on your own machine

### Once per machine

1. **Ollama + the model** (AI-written summaries; the app also works without it)
   ```bash
   curl -fsSL https://ollama.com/install.sh | sh
   ollama pull qwen2.5:7b-instruct
   ```
2. **Tailscale** (gives the demo a fixed public link) - free account at https://tailscale.com (sign in with Google is fine)
   ```bash
   curl -fsSL https://tailscale.com/install.sh | sh
   sudo tailscale up                       # opens a sign-in link - sign in, approve this computer
   sudo tailscale set --operator=$USER     # lets the demo script manage the link without sudo
   ```
3. **First start** - run the demo command below once. If it prints a `login.tailscale.com/...` link, open it,
   click **Enable** (this switches on Funnel and HTTPS for your account), then run the command again.

Turn off automatic reboots for system updates on this machine during the hackathon.

### Every time you run the demo

Use the normal **Terminal** app (not the VS Code terminal - closing VS Code would stop the demo):

```bash
cd Healthathon_ClinieSync/cliniesync
scripts/start_demo.sh --fixed
```

It checks the machine, starts the app and prints the link:

```
  ClinieSync is live
  Link to share:   https://<this-computer>.<your-tailnet>.ts.net
```

**That link never changes** - put it in the hackathon submission once. After a restart, crash or reboot, just run the
same command again and the same link works.

Sign in with a role card - password `demo123`:
**Dr. Ananya Rao** (doctor) · **Rekha S.** (care coordinator) · **Hospital Administrator**.

- The computer must stay **on, online and plugged in**; the script stops it from sleeping while it runs.
- **Ctrl+C** stops the app (the link then shows an error until you start it again).
- Want it to survive closing the terminal window too? Start it inside tmux:
  `tmux new -s demo` → run the command → press **Ctrl+B** then **D** to leave it running. Back later: `tmux attach -t demo`.
- Just testing on your own machine? `scripts/start_demo.sh --local` → http://localhost:8000
- No Tailscale? `scripts/start_demo.sh` gives a temporary trycloudflare.com link instead (changes every run;
  needs `sudo apt install ./cloudflared-linux-amd64.deb` once).

## If something goes wrong

The script stops with a plain message telling you what to do. The common ones:

| Message | What to do |
|---|---|
| Python environment … built for a different kind of computer | `rm -rf .venv && scripts/setup.sh` once (needs Python 3.12, a few minutes), then start again |
| Tailscale is not signed in | `sudo tailscale up`, then start again |
| Could not switch the fixed link on … `login.tailscale.com` link | Open the link, click Enable, start again |
| Could not switch the fixed link on … access denied | `sudo tailscale set --operator=$USER`, start again |
| Ollama is not running | `ollama serve` in another terminal (or `sudo systemctl start ollama`), then start again |
| Port 8000 is already in use | It is already running in another terminal / tmux - or `PORT=8001 scripts/start_demo.sh --fixed` |

Full logs: `data/logs/app.log` (and `data/logs/tunnel.log` for the temporary link).
To take the fixed link offline completely after the hackathon: `tailscale funnel reset`.

## E-mail (Share report)

Reports are e-mailed from the team account **cliniesync.care@gmail.com**; the settings are in `.env`.
To demo it: doctor → Patient Journey → *Summarize journey* → **Verify** → **Share report** → *Someone else* → your e-mail
→ tick **E-mail** and the consent box → **Share report**. First mails may land in spam.

- `.env` holds the account's app password and the login signing key - share this folder only privately, never in a
  public link or on GitHub.
- To pause sending, set `DELIVERY_MODE=sandbox` in `.env` (messages are then only saved to `data/outbox/`).
- If the password ever leaks: Google Account → Security → App passwords → delete it, create a new one, and run
  `.venv/bin/python scripts/setup_email.py`.

## Housekeeping

- Clear demo clicks before a fresh demo (keeps the patient data): `.venv/bin/python scripts/reset_activity.py --all`
- Windows: use WSL (Ubuntu) and follow the same steps inside it.
