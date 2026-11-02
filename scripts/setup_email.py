"""One-time setup for free, direct e-mail delivery of shared reports (SMTP), then a test mail.

    .venv/bin/python scripts/setup_email.py              # Gmail (default)
    .venv/bin/python scripts/setup_email.py --test-only  # just send a test mail with the current .env

Gmail: the password is an *app password*, not your normal password.
  Google Account -> Security -> 2-Step Verification (turn on) -> App passwords -> create "ClinieSync"
  -> copy the 16-character code.  Free; Gmail allows about 500 mails per day.
Other providers work too (Outlook: smtp-mail.outlook.com:587, Brevo: smtp-relay.brevo.com:587, ...).
The values are written to .env (git-ignored). Restart the server afterwards.
"""
from __future__ import annotations

import argparse
import getpass
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENV = ROOT / ".env"
sys.path.insert(0, str(ROOT))


def _update_env(values: dict[str, str]) -> None:
    lines = ENV.read_text(encoding="utf-8").splitlines() if ENV.exists() else []
    done = set()
    for i, line in enumerate(lines):
        key = line.split("=", 1)[0].strip()
        if key in values:
            lines[i] = f"{key}={values[key]}"
            done.add(key)
    lines += [f"{k}={v}" for k, v in values.items() if k not in done]
    ENV.write_text("\n".join(lines) + "\n", encoding="utf-8")
    ENV.chmod(0o600)                                    # the app password stays readable only by you


def _send_test(to: str) -> bool:
    from common.settings import get_settings
    from backend.app.services.notify.providers import SMTPEmail, channel_live

    get_settings.cache_clear()
    if not channel_live("email"):
        print("E-mail is not configured (or DELIVERY_MODE=sandbox).")
        return False
    res = SMTPEmail().send(to, "ClinieSync test: e-mail delivery of shared reports is working.",
                           subject="ClinieSync - test e-mail",
                           html="<p><b>ClinieSync</b>: e-mail delivery of shared reports is working.</p>")
    print(("OK - " if res.ok else "FAILED - ") + res.detail)
    return res.ok


def main() -> None:
    ap = argparse.ArgumentParser(description="Set up direct e-mail delivery (SMTP) for Share Report")
    ap.add_argument("--test-only", action="store_true", help="only send a test mail with the current settings")
    a = ap.parse_args()
    if not a.test_only:
        print("ClinieSync e-mail setup (press Enter to accept the value in brackets)\n")
        host = input("SMTP server [smtp.gmail.com]: ").strip() or "smtp.gmail.com"
        port = input("Port [587]: ").strip() or "587"
        user = input("Sender e-mail address (login): ").strip()
        if not re.match(r"^[^@\s]+@[^@\s]+\.[a-z]{2,}$", user, re.I):
            sys.exit("That does not look like an e-mail address.")
        pwd = getpass.getpass("App password (input hidden): ").replace(" ", "")
        name = input("Sender name shown to recipients [ClinieSync Clinic]: ").strip() or "ClinieSync Clinic"
        values = {"SMTP_HOST": host, "SMTP_PORT": port, "SMTP_USER": user, "SMTP_PASSWORD": pwd, "SMTP_FROM": user,
                  "SMTP_FROM_NAME": name, "DELIVERY_MODE": "auto"}
        _update_env(values)
        os.environ.update(values)
        print(f"\nSaved to {ENV} (permissions 600).")
    to = input("Send a test e-mail to [same address]: ").strip() or os.getenv("SMTP_USER", "")
    if to and _send_test(to):
        print("\nDone. Restart the ClinieSync server; Share report -> E-mail will now deliver directly.")
    elif to:
        print("\nCheck the address, app password and server, then run:  .venv/bin/python scripts/setup_email.py")


if __name__ == "__main__":
    main()
