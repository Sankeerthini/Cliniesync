"""Message delivery: e-mail (free, direct from the server), plus optional paid SMS / WhatsApp gateways.

DELIVERY_MODE=auto (default)
  * E-mail  - sent for real by SMTP as soon as SMTP_* is configured (e.g. Gmail + app password:
              free, ~500 mails/day; set it up with `python scripts/setup_email.py`).
  * SMS / WhatsApp - sent by the server ONLY if a paid gateway is configured (Twilio / Meta WhatsApp
              Cloud API). Otherwise Share Report hands them to the doctor's device instead (free:
              WhatsApp click-to-chat link, phone SMS app) - see report_service.
DELIVERY_MODE=sandbox - nothing leaves the machine; messages are written to data/outbox/.
(DELIVERY_MODE=live is treated like auto.)

Contacts typed in by the doctor ("Someone else") are delivered to. Contacts on record are delivered to only
if listed in DELIVERY_ALLOWLIST, which prevents messages to the fake numbers / e-mails in synthetic data.
"""
from __future__ import annotations

import os
import smtplib
from dataclasses import dataclass
from datetime import datetime
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr

import httpx

from common.settings import get_settings


@dataclass
class DeliveryResult:
    ok: bool
    provider: str
    detail: str


class SandboxProvider:
    def __init__(self, channel: str):
        self.channel = channel
        self.name = f"sandbox-{channel}"

    def send(self, to: str, body: str, subject: str | None = None, html: str | None = None,
             message_id: str = "") -> DeliveryResult:
        s = get_settings()
        folder = s.outbox_dir / datetime.now().strftime("%Y-%m-%d")
        folder.mkdir(parents=True, exist_ok=True)
        stem = f"{datetime.now():%H%M%S}_{self.channel}_{message_id or 'msg'}"
        (folder / f"{stem}.txt").write_text(f"TO: {to}\nSUBJECT: {subject or '-'}\n\n{body}", encoding="utf-8")
        if html:
            (folder / f"{stem}.html").write_text(html, encoding="utf-8")
        return DeliveryResult(True, self.name, f"sandbox - not delivered; saved to outbox/{folder.name}/{stem}")


class TwilioSMS:
    name = "twilio-sms"

    def send(self, to, body, subject=None, html=None, message_id=""):
        s = get_settings()
        r = httpx.post(f"https://api.twilio.com/2010-04-01/Accounts/{s.twilio_account_sid}/Messages.json",
                       data={"To": to, "From": s.twilio_from_number, "Body": body},
                       auth=(s.twilio_account_sid, s.twilio_auth_token), timeout=20)
        return DeliveryResult(r.status_code < 300, self.name, f"HTTP {r.status_code}")


class WhatsAppCloud:
    name = "whatsapp-cloud"

    def send(self, to, body, subject=None, html=None, message_id=""):
        s = get_settings()
        version = os.getenv("WHATSAPP_API_VERSION", "v21.0")
        r = httpx.post(f"https://graph.facebook.com/{version}/{s.whatsapp_phone_number_id}/messages",
                       headers={"Authorization": f"Bearer {s.whatsapp_token}"},
                       json={"messaging_product": "whatsapp", "to": to.lstrip("+"), "type": "text",
                             "text": {"body": body[:4000]}}, timeout=20)
        return DeliveryResult(r.status_code < 300, self.name, f"HTTP {r.status_code}")


class SMTPEmail:
    name = "smtp-email"

    def send(self, to, body, subject=None, html=None, message_id="", attachment: tuple[str, str] | None = None):
        """`attachment` = (file name, HTML text), e.g. the full report so it can be saved or printed."""
        s = get_settings()
        msg = MIMEMultipart("mixed")
        msg["Subject"], msg["To"] = subject or "ClinieSync", to
        msg["From"] = formataddr((s.smtp_from_name, s.smtp_from or s.smtp_user))
        alt = MIMEMultipart("alternative")
        alt.attach(MIMEText(body, "plain", "utf-8"))
        if html:
            alt.attach(MIMEText(html, "html", "utf-8"))
        msg.attach(alt)
        if attachment:
            part = MIMEText(attachment[1], "html", "utf-8")
            part.add_header("Content-Disposition", "attachment", filename=attachment[0])
            msg.attach(part)
        if s.smtp_port == 465:                                   # implicit TLS
            srv = smtplib.SMTP_SSL(s.smtp_host, s.smtp_port, timeout=20, context=ssl.create_default_context())
        else:
            srv = smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=20)
        with srv:
            srv.ehlo()
            if s.smtp_port != 465 and srv.has_extn("starttls"):
                srv.starttls(context=ssl.create_default_context())
                srv.ehlo()
            if s.smtp_user:
                srv.login(s.smtp_user, s.smtp_password)
            refused = srv.send_message(msg)
        if refused:
            return DeliveryResult(False, self.name, f"refused by mail server: {refused}")
        return DeliveryResult(True, self.name, f"delivered to the mail server ({s.smtp_host}) for {to}")


def _configured(channel: str) -> bool:
    s = get_settings()
    return {"sms": bool(s.twilio_account_sid and s.twilio_auth_token and s.twilio_from_number),
            "whatsapp": bool(s.whatsapp_token and s.whatsapp_phone_number_id),
            "email": bool(s.smtp_host and (s.smtp_from or s.smtp_user))}.get(channel, False)


def channel_live(channel: str) -> bool:
    """True when this channel really leaves the machine (provider configured and not in sandbox mode)."""
    return get_settings().delivery_mode != "sandbox" and _configured(channel)


def deliver(channel: str, to: str, body: str, subject: str | None = None, html: str | None = None,
            message_id: str = "", explicit: bool = False, attachment: tuple[str, str] | None = None) -> DeliveryResult:
    """`explicit` = the doctor typed this recipient in (not a contact taken from the record)."""
    s = get_settings()
    if channel_live(channel):
        if not explicit and to not in s.delivery_allowlist:
            return DeliveryResult(False, "allowlist", f"recipient {to} is not in DELIVERY_ALLOWLIST - not sent")
        provider = {"sms": TwilioSMS, "whatsapp": WhatsAppCloud, "email": SMTPEmail}[channel]()
        try:
            if channel == "email":
                return provider.send(to, body, subject, html, message_id, attachment=attachment)
            return provider.send(to, body, subject, html, message_id)
        except smtplib.SMTPAuthenticationError:
            return DeliveryResult(False, provider.name, "mail server rejected the login - check SMTP_USER / SMTP_PASSWORD "
                                                        "(Gmail needs an app password)")
        except Exception as exc:
            return DeliveryResult(False, provider.name, f"{type(exc).__name__}: {exc}")
    return SandboxProvider(channel).send(to, body, subject, html, message_id)


def delivery_status() -> dict:
    """Per channel: 'live' (server sends), 'device' (SMS/WhatsApp handed to the doctor's phone, free),
    'not_configured' (e-mail without SMTP) or 'sandbox'."""
    s = get_settings()

    def state(c: str) -> str:
        if s.delivery_mode == "sandbox":
            return "sandbox"
        if _configured(c):
            return "live"
        return "not_configured" if c == "email" else "device"
    return {"mode": s.delivery_mode, "channels": {c: state(c) for c in ("sms", "whatsapp", "email")},
            "email_from": (s.smtp_from or s.smtp_user) if _configured("email") else None,
            "allowlist_size": len(s.delivery_allowlist)}
