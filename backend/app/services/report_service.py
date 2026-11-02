"""'Share Report' - a doctor-verified, structured visit summary sent to the patient/caregiver.

Rules enforced here (not just in the UI):
  * only doctors can share; only VERIFIED / EDITED responses about one patient can be shared
  * patient / caregiver: consent for the channel must be on record AND re-confirmed by the doctor
  * someone else ("other"): the doctor types the mobile number / e-mail and confirms the patient agreed to share
    with that person; the contact is validated and only its last digits are written to the audit trail
  * e-mail is delivered directly by the server (SMTP, e.g. Gmail app password - free); the report is the mail body
    and is also attached as an HTML file
  * WhatsApp / SMS use no paid gateway by default: the doctor gets a click-to-chat link (wa.me) / SMS-app link with
    the message and the report link filled in (a paid gateway is used only if one is configured)
  * every message carries an expiring, unguessable link to the full report (/r/<token>)
  * structure and labels come from reviewed templates (en/hi/bn/kn); the doctor's
    verified note is translated only with a visible "machine translation" label and
    the English original kept beneath it
"""
from __future__ import annotations

import html as H
import re
import secrets
import uuid
from datetime import date, datetime, timedelta
from urllib.parse import quote

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ai.orchestrator import UserCtx
from ai.translate.templates import LANGUAGES, VISIT_TYPE_NAMES, label
from ai.translate.translator import translate
from backend.app.services.audit import audit
from backend.app.services.notify.providers import channel_live, deliver
from common.settings import get_settings
from database import models as M

FONT = {"en": "Noto Sans", "hi": "Noto Sans Devanagari", "bn": "Noto Sans Bengali", "kn": "Noto Sans Kannada"}


def _clean_note(text: str) -> str:
    text = re.sub(r"\[S\d+\]", "", text or "")
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    return re.sub(r"[ \t]+\n", "\n", text).strip()


def _load(s: Session, response_id: str, user: UserCtx) -> tuple[M.AIResponse, M.Patient]:
    r = s.get(M.AIResponse, response_id)
    if not r:
        raise HTTPException(404, "response not found")
    if r.status not in ("verified", "edited"):
        raise HTTPException(409, "the response must be verified by a clinician before it can be shared")
    if not r.patient_id:
        raise HTTPException(409, "only patient-specific responses can be shared as a report")
    if user.role != "doctor":
        raise HTTPException(403, "only doctors can share reports")
    return r, s.get(M.Patient, r.patient_id)


def build(s: Session, response_id: str, language: str, user: UserCtx, ref: date) -> dict:
    if language not in LANGUAGES:
        raise HTTPException(400, f"language must be one of {list(LANGUAGES)}")
    r, p = _load(s, response_id, user)
    L = lambda k: label(k, language)  # noqa: E731
    fac = {f.facility_id: f.name for f in s.scalars(select(M.Facility))}
    facility = fac.get(p.facility_id, "")
    preg = s.scalars(select(M.Pregnancy).where(M.Pregnancy.patient_id == p.patient_id).order_by(M.Pregnancy.lmp.desc())).first()
    visits = list(s.scalars(select(M.Visit).where(M.Visit.patient_id == p.patient_id, M.Visit.status == "completed")
                            .order_by(M.Visit.visit_date.desc()).limit(6)))
    tests = list(s.scalars(select(M.Investigation).where(M.Investigation.patient_id == p.patient_id)
                           .order_by(M.Investigation.ordered_on.desc()).limit(8)))
    nxt = list(s.scalars(select(M.FollowUp).where(M.FollowUp.patient_id == p.patient_id,
                                                  M.FollowUp.status.in_(["upcoming", "due", "overdue"]))
                         .order_by(M.FollowUp.due_on).limit(4)))
    note_en = _clean_note(r.final_text or r.answer_text)
    note_tr, engine = translate(note_en, language) if language != "en" else (note_en, "none")
    doctor = user.display_name
    today = ref.strftime("%d-%m-%Y")

    def vt(v):
        return VISIT_TYPE_NAMES.get(v.visit_category, {}).get(language, v.visit_type) + f" ({v.visit_type})"

    from ai.translate.templates import VISIT_NAMES

    next_items = [f"{VISIT_NAMES.get(f.followup_type, {}).get(language, f.followup_type)} - {f.due_on:%d-%m-%Y}" for f in nxt]
    rows_v = "".join(f"<tr><td>{v.visit_date:%d-%m-%Y}</td><td>{H.escape(vt(v))}</td><td>{H.escape(fac.get(v.facility_id, ''))}</td></tr>"
                     for v in visits)
    rows_t = "".join(f"<tr><td>{H.escape(t.test_name)}</td><td>{t.ordered_on:%d-%m-%Y}</td><td>"
                     f"{H.escape(t.result_summary) if t.result_summary else L('awaited')}</td></tr>" for t in tests)
    note_block = (f"<p class='note'>{H.escape(note_tr).replace(chr(10), '<br>')}</p>"
                  f"<p class='mt'>{L('machine_translated')} · {engine}</p>"
                  f"<details><summary>English</summary><p class='note'>{H.escape(note_en).replace(chr(10), '<br>')}</p></details>"
                  if note_tr and language != "en" else
                  f"<p class='mt'>{L('note_in_english')}</p><p class='note'>{H.escape(note_en).replace(chr(10), '<br>')}</p>")
    preg_block = (f"<h2>{L('pregnancy')}</h2><p>{L('lmp')}: <b>{preg.lmp:%d-%m-%Y}</b> · {L('edd')}: <b>{preg.edd:%d-%m-%Y}</b></p>"
                  if preg else "")
    font = FONT[language]
    html = f"""<!doctype html><html lang="{language}"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{L('title')} - {H.escape(p.full_name)}</title>
<link href="https://fonts.googleapis.com/css2?family={font.replace(' ', '+')}:wght@400;600&display=swap" rel="stylesheet">
<style>body{{font-family:'{font}','Noto Sans',system-ui,sans-serif;color:#10242b;background:#fff;max-width:720px;margin:24px auto;padding:0 16px;line-height:1.55}}
header{{border-bottom:3px solid #0f7c80;padding-bottom:10px;margin-bottom:12px}}h1{{color:#0f7c80;margin:0;font-size:24px}}
h2{{font-size:16px;color:#0b5c60;margin:18px 0 6px}}table{{width:100%;border-collapse:collapse;font-size:14px}}
td,th{{border-bottom:1px solid #d7e3e5;padding:6px 4px;text-align:left}}.meta{{color:#405a61;font-size:14px}}
.note{{background:#f1f8f8;border-left:4px solid #0f7c80;padding:10px 12px;white-space:normal}}.mt{{color:#5b6f74;font-size:12px}}
footer{{margin-top:20px;font-size:12px;color:#405a61;border-top:1px solid #d7e3e5;padding-top:10px}}</style></head><body>
<header><h1>{L('title')}</h1><div class="meta">{L('patient')}: <b>{H.escape(p.full_name)}</b> ({p.patient_id}) ·
{L('facility')}: <b>{H.escape(facility)}</b><br>{L('verified_by')}: <b>{H.escape(doctor)}</b> · {L('date')}: {today}</div></header>
{preg_block}
<h2>{L('visits')}</h2><table><tr><th>{L('date')}</th><th>{L('visit')}</th><th>{L('facility')}</th></tr>{rows_v}</table>
<h2>{L('tests')}</h2><table><tr><th>{L('test')}</th><th>{L('date')}</th><th>{L('result')}</th></tr>{rows_t}</table>
<h2>{L('next')}</h2><p>{'<br>'.join(H.escape(x) for x in next_items) or L('none')}</p>
<h2>{L('doctor_note')}</h2>{note_block}
<footer>{L('footer')}<br>ClinieSync · SYNTHETIC DEMO DATA</footer></body></html>"""
    sms = label("sms", language).format(facility=facility, date=today, doctor=doctor,
                                        next=next_items[0] if next_items else L("none"))
    wa = "\n".join([f"*{L('title')}* - {p.full_name}", f"{L('facility')}: {facility}", f"{L('verified_by')}: {doctor} · {today}",
                    *( [f"{L('lmp')}: {preg.lmp:%d-%m-%Y} · {L('edd')}: {preg.edd:%d-%m-%Y}"] if preg else []),
                    "", f"*{L('next')}*", *(next_items or [L("none")]), "", f"*{L('doctor_note')}*",
                    (note_tr if note_tr else note_en)[:1500], "", L("footer")])
    return {"html": html, "sms_text": sms, "whatsapp_text": wa, "language": language, "translation_engine": engine,
            "patient": {"patient_id": p.patient_id, "name": p.full_name, "preferred_language": p.preferred_language},
            "consent": {"sms": p.consent_sms, "whatsapp": p.consent_whatsapp, "email": p.consent_email},
            "recipients": {"patient_phone": p.phone, "caregiver_phone": p.caregiver_phone, "email": p.email}}


_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[a-z]{2,}$", re.I)


def normalize_phone(raw: str | None) -> str | None:
    """'98450 12345' / '098450-12345' / '919845012345' / '+91 98450 12345' -> '+919845012345'. None if invalid."""
    if not raw or not raw.strip():
        return None
    plus = raw.strip().startswith("+")
    d = re.sub(r"\D", "", raw)
    if plus:
        return f"+{d}" if 8 <= len(d) <= 15 else None
    d = d.lstrip("0")
    if len(d) == 10 and d[0] in "6789":                 # Indian mobile without country code
        return f"+91{d}"
    if len(d) == 12 and d.startswith("91") and d[2] in "6789":
        return f"+{d}"
    return None


def _mask(addr: str) -> str:
    if "@" in addr:
        user, dom = addr.split("@", 1)
        return f"{user[:2]}***@{dom}"
    return f"{addr[:3]}******{addr[-3:]}"


def _device_links(channels: list[str], phone: str | None, texts: dict[str, str]) -> dict[str, str]:
    """Free hand-off to the doctor's device: WhatsApp click-to-chat and the phone's SMS app, message pre-filled."""
    links = {}
    if "whatsapp" in channels and phone:
        links["whatsapp"] = f"https://wa.me/{phone.lstrip('+')}?text={quote(texts['whatsapp'])}"
    if "sms" in channels and phone:
        links["sms"] = f"sms:{phone}?&body={quote(texts['sms'])}"
    return links


def share(s: Session, response_id: str, language: str, channels: list[str], recipient: str, consent_confirmed: bool,
          user: UserCtx, ref: date, to_name: str | None = None, to_phone: str | None = None,
          to_email: str | None = None, base_url: str | None = None) -> dict:
    if not consent_confirmed:
        raise HTTPException(400, "please confirm the patient's consent for these channels")
    if not channels:
        raise HTTPException(400, "choose at least one channel")
    rep = build(s, response_id, language, user, ref)
    r, p = _load(s, response_id, user)
    st = get_settings()

    if recipient == "other":
        phone = normalize_phone(to_phone)
        email = to_email.strip() if to_email and to_email.strip() else None
        if to_phone and to_phone.strip() and not phone:
            raise HTTPException(422, "mobile number not recognised - use 10 digits (e.g. 98450 12345) or +<country code>")
        if email and not _EMAIL.match(email):
            raise HTTPException(422, "e-mail address not recognised")
        if not phone and not email:
            raise HTTPException(422, "enter a mobile number or an e-mail address")
        addr = {"sms": phone, "whatsapp": phone, "email": email}
        allowed = {"sms": True, "whatsapp": True, "email": True}
    else:
        addr = {"sms": p.caregiver_phone if recipient == "caregiver" else p.phone,
                "whatsapp": p.caregiver_phone if recipient == "caregiver" else p.phone, "email": p.email}
        allowed = rep["consent"]

    report_id = uuid.uuid4().hex[:16]
    subject = f"{label('title', language)} - {p.full_name}"
    base = (st.public_base_url or (base_url or "").rstrip("/"))
    link = None
    if base.startswith(("http://", "https://")):
        token = secrets.token_urlsafe(24)
        s.add(M.ReportLink(token=token, report_id=report_id, created_at=datetime.now(),
                           expires_at=datetime.now() + timedelta(days=st.report_link_days), created_by=user.username))
        link = f"{base}/r/{token}"
    greet = f"{to_name.strip()},\n" if recipient == "other" and to_name and to_name.strip() else ""
    tail = f"\n\n{label('title', language)}: {link}" if link else ""
    texts = {"sms": greet + rep["sms_text"] + (f" {link}" if link else ""),
             "whatsapp": greet + rep["whatsapp_text"] + tail,
             "email": greet + rep["whatsapp_text"] + tail}
    html = rep["html"] if not link else rep["html"].replace(
        "<header>", f"<p style='font-size:13px'><a href='{H.escape(link)}'>{H.escape(link)}</a></p><header>", 1)

    results = []
    for ch in channels:
        to = addr.get(ch)
        if not allowed.get(ch):
            results.append({"channel": ch, "status": "skipped", "detail": "no consent on record for this channel"})
            continue
        if not to:
            results.append({"channel": ch, "status": "skipped",
                            "detail": "no mobile number entered" if ch != "email" and recipient == "other" else
                            "no e-mail entered" if recipient == "other" else "no address on record"})
            continue
        if ch in ("sms", "whatsapp") and st.delivery_mode != "sandbox" and not channel_live(ch):
            # no paid gateway: hand the prepared message to the doctor's device (free)
            status, detail, sandbox = "device", ("open WhatsApp below - the message and report link are filled in"
                                                 if ch == "whatsapp" else "open the SMS app below - message filled in"), False
        elif ch == "email" and st.delivery_mode != "sandbox" and not channel_live("email"):
            status, detail, sandbox = "failed", ("e-mail server not set up - run `python scripts/setup_email.py` "
                                                 "(free with a Gmail app password), then restart the server"), False
        else:
            fname = f"ClinieSync_report_{p.patient_id}_{ref:%Y%m%d}.html"
            res = deliver(ch, to, texts[ch], subject=subject, html=html if ch == "email" else None,
                          message_id=report_id, explicit=recipient == "other",
                          attachment=(fname, rep["html"]) if ch == "email" else None)
            status, detail, sandbox = ("sent" if res.ok else "failed"), f"{res.provider}: {res.detail}", \
                res.provider.startswith("sandbox")
        s.add(M.OutboxMessage(message_id=uuid.uuid4().hex[:16], created_at=datetime.now(), kind="report",
                              report_id=report_id, patient_id=p.patient_id, recipient_type=recipient, recipient=to,
                              channel=ch, language=language, subject=label("title", language), body=texts[ch],
                              status={"device": "handed_to_device"}.get(status, status), created_by=user.username,
                              approved_by=user.username, sent_at=datetime.now(), delivery_detail=detail))
        results.append({"channel": ch, "to": _mask(to), "status": status, "sandbox": sandbox, "detail": detail})
    ok = any(x["status"] in ("sent", "device") for x in results)
    s.add(M.Report(report_id=report_id, created_at=datetime.now(), response_id=response_id, patient_id=p.patient_id,
                   language=language, html=rep["html"], short_text=rep["sms_text"], created_by=user.username,
                   channels=results, status="shared" if ok else "failed"))
    audit(s, user, "share_report", target=p.patient_id, decision="shared" if ok else "failed", report_id=report_id,
          language=language, recipient=recipient, channels=[x["channel"] for x in results if x["status"] == "sent"],
          to=sorted({x["to"] for x in results if x.get("to")}), link_created=bool(link))
    usable = [c for c in channels if allowed.get(c)]
    return {"report_id": report_id, "results": results, "status": "shared" if ok else "failed",
            "report_url": link, "link_expires_days": st.report_link_days if link else None,
            "device_links": _device_links(usable, addr["sms"], texts)}


def public_report(s: Session, token: str) -> str | None:
    """HTML of a shared report for a valid, unexpired link (no login); None otherwise."""
    lk = s.get(M.ReportLink, token)
    if not lk or lk.expires_at < datetime.now():
        return None
    rep = s.get(M.Report, lk.report_id)
    if not rep:
        return None
    lk.views = (lk.views or 0) + 1
    return rep.html
