# Running the ClinieSync demo

Everything needed is in this folder: the app, the built UI, the synthetic data and a ready Python environment for Linux.
You only add two things to your machine (once), then start it with one command.

## Once per machine

1. **Ollama + the model** (for AI-written summaries; the app also works without it)
   ```bash
   curl -fsSL https://ollama.com/install.sh | sh
   ollama pull qwen2.5:7b-instruct
   ```
2. **cloudflared** (makes the public link) - the Ubuntu/Debian installer is in this folder:
   ```bash
   sudo apt install ./cloudflared-linux-amd64.deb
   ```

## Every time you run the demo

```bash
cd cliniesync
scripts/start_demo.sh
```

It checks the machine, starts the app, opens the public link and prints it:

```
  ClinieSync is live
  Link to share:   https://some-random-words.trycloudflare.com
```

Share that link. Sign in with a role card - password `demo123`:
**Dr. Ananya Rao** (doctor) · **Rekha S.** (care coordinator) · **Hospital Administrator**.

- Keep the terminal open and the laptop plugged in (the script stops it from sleeping while it runs).
- **Ctrl+C** stops everything.
- The link **changes every time** the script restarts - share the new one.
- Just testing on your own machine? `scripts/start_demo.sh --local` → http://localhost:8000

## If something goes wrong

The script stops with a plain message telling you what to do. The common ones:

| Message | What to do |
|---|---|
| Python environment … built for a different kind of computer | `rm -rf .venv && scripts/setup.sh` once (needs Python 3.12, a few minutes), then start again |
| Ollama is not running | `ollama serve` in another terminal (or `sudo systemctl start ollama`), then start again |
| cloudflared is not installed | `sudo apt install ./cloudflared-linux-amd64.deb` |
| Port 8000 is already in use | It is already running in another terminal - or `PORT=8001 scripts/start_demo.sh` |
| The tunnel stopped | Internet dropped - Ctrl+C and start again, share the new link |

Full logs: `data/logs/app.log` and `data/logs/tunnel.log`.

## E-mail (Share report)

Reports are e-mailed from the team account **cliniesync.care@gmail.com**; the settings are in `.env`.
To demo it: doctor → Patient Journey → *Summarize journey* → **Verify** → **Share report** → *Someone else* → your e-mail
→ tick **E-mail** and the consent box → **Share report**. First mails may land in spam.

- `.env` holds the account's app password - share this folder only privately, never in a public link or on GitHub.
- To pause sending, set `DELIVERY_MODE=sandbox` in `.env` (messages are then only saved to `data/outbox/`).
- If the password ever leaks: Google Account → Security → App passwords → delete it, create a new one, and run
  `.venv/bin/python scripts/setup_email.py`.

## Housekeeping

- Clear demo clicks before a fresh demo (keeps the patient data): `.venv/bin/python scripts/reset_activity.py --all`
- Windows: use WSL (Ubuntu) and follow the same steps inside it.
