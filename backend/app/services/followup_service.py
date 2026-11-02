"""Care coordination: follow-up queue, reminder drafting, approval-gated sending, contact log.

Human-in-the-loop by construction:
  draft (system)  ->  approve (human)  ->  send (system, sandbox/live)  ->  contact outcome (human)
Nothing is sent without an explicit approval recorded in the audit trail.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ai.orchestrator import UserCtx
from ai.translate.templates import reminder_text
from backend.app.services.audit import audit
from common.settings import get_settings
from backend.app.services.notify.providers import deliver
from database import models as M

OPEN = ["due", "overdue", "missed"]


def queue(s: Session, ref: date, status: list[str] | None = None, ftype: str = "", facility_id: str = "",
          q: str = "", limit: int = 300) -> list[dict]:
    stmt = select(M.FollowUp, M.Patient).join(M.Patient, M.Patient.patient_id == M.FollowUp.patient_id) \
        .where(M.FollowUp.status.in_(status or ["due", "overdue"]))
    if ftype:
        stmt = stmt.where(M.FollowUp.followup_type == ftype)
    if facility_id:
        stmt = stmt.where(M.FollowUp.facility_id == facility_id)
    if q:
        stmt = stmt.where(M.Patient.full_name.ilike(f"%{q}%") | M.Patient.patient_id.ilike(f"%{q}%"))
    fac = {f.facility_id: f.name for f in s.scalars(select(M.Facility))}
    rows = []
    for f, p in s.execute(stmt.limit(2000)).all():
        rows.append({"followup_id": f.followup_id, "patient_id": p.patient_id, "patient": p.full_name,
                     "followup_type": f.followup_type, "due_on": f.due_on.isoformat(),
                     "days_past_due": max(0, (ref - f.due_on).days), "status": f.status,
                     "facility": fac.get(f.facility_id), "language": p.preferred_language, "phone": p.phone,
                     "caregiver": f"{p.caregiver_name} ({p.caregiver_relation})" if p.caregiver_name else None,
                     "consent_sms": p.consent_sms, "consent_whatsapp": p.consent_whatsapp,
                     "workflow_state": f.workflow_state, "contact_attempts": f.contact_attempts,
                     "last_contact_on": f.last_contact_on.isoformat() if f.last_contact_on else None,
                     "documented_instruction": f.description, "origin": f.origin, "source_doc_id": f.source_doc_id})
    rows.sort(key=lambda r: (-r["days_past_due"], r["due_on"]))
    return rows[:limit]


def summary(s: Session, ref: date) -> dict:
    counts = dict(s.execute(select(M.FollowUp.status, func.count()).group_by(M.FollowUp.status)).all())
    open_rows = s.execute(select(M.FollowUp.due_on, M.FollowUp.followup_type)
                          .where(M.FollowUp.status.in_(["overdue", "missed"]))).all()
    buckets = {"1-7 days": 0, "8-14 days": 0, "15-28 days": 0, "29-60 days": 0, "> 60 days": 0}
    for due, _ in open_rows:
        d = (ref - due).days
        key = "1-7 days" if d <= 7 else "8-14 days" if d <= 14 else "15-28 days" if d <= 28 else \
            "29-60 days" if d <= 60 else "> 60 days"
        buckets[key] += 1
    by_type = dict(s.execute(select(M.FollowUp.followup_type, func.count())
                             .where(M.FollowUp.status.in_(["due", "overdue"])).group_by(M.FollowUp.followup_type)).all())
    pending_approval = s.scalar(select(func.count()).select_from(M.OutboxMessage).where(M.OutboxMessage.status == "draft"))
    return {"counts": counts, "aging": [{"bucket": k, "followups": v} for k, v in buckets.items()],
            "open_by_type": [{"followup_type": k, "open": v} for k, v in by_type.items()],
            "drafts_awaiting_approval": pending_approval or 0}


def create_drafts(s: Session, user: UserCtx, ref: date, followup_ids: list[str], recipient: str = "patient",
                  channel: str = "sms", language: str = "auto") -> list[dict]:
    fac = {f.facility_id: f for f in s.scalars(select(M.Facility))}
    out = []
    for fid in followup_ids[:100]:
        f = s.get(M.FollowUp, fid)
        if not f:
            continue
        p = s.get(M.Patient, f.patient_id)
        lang = p.preferred_language if language == "auto" else language
        consent = {"sms": p.consent_sms, "whatsapp": p.consent_whatsapp, "email": p.consent_email}.get(channel, False)
        to_caregiver = recipient == "caregiver"
        to = (p.caregiver_phone if to_caregiver else p.phone) if channel != "email" else p.email
        body = reminder_text(lang, overdue=f.due_on < ref, name=(p.caregiver_name if to_caregiver else p.full_name).split(" ")[0],
                             facility=fac[f.facility_id].name, followup_type=f.followup_type,
                             date_str=f.due_on.strftime("%d-%m-%Y"), phone=get_settings().clinic_helpline,
                             patient_name=p.full_name.split(" ")[0] if to_caregiver else None)
        status = "draft" if (consent and to) else "blocked_no_consent"
        msg = M.OutboxMessage(message_id=uuid.uuid4().hex[:16], created_at=datetime.now(), kind="followup_reminder",
                              followup_id=f.followup_id, patient_id=p.patient_id, recipient_type=recipient,
                              recipient=to or "-", channel=channel, language=lang, subject=None, body=body,
                              status=status, created_by=user.username)
        s.add(msg)
        if status == "draft":
            f.workflow_state = "reminder_drafted"
        out.append(_msg(msg))
    audit(s, user, "draft_reminders", decision="drafted", count=len(out), channel=channel, recipient=recipient)
    return out


def list_outbox(s: Session, status: str = "", kind: str = "") -> list[dict]:
    stmt = select(M.OutboxMessage)
    if status:
        stmt = stmt.where(M.OutboxMessage.status == status)
    if kind:
        stmt = stmt.where(M.OutboxMessage.kind == kind)
    names = dict(s.execute(select(M.Patient.patient_id, M.Patient.full_name)).all())
    return [{**_msg(m), "patient": names.get(m.patient_id)}
            for m in s.scalars(stmt.order_by(M.OutboxMessage.created_at.desc()).limit(300))]


def act_on_message(s: Session, user: UserCtx, message_id: str, action: str, body: str | None = None) -> dict:
    m = s.get(M.OutboxMessage, message_id)
    if not m:
        raise HTTPException(404, "message not found")
    if action == "edit":
        if m.status != "draft":
            raise HTTPException(409, "only drafts can be edited")
        m.body = body or m.body
    elif action == "approve":
        if m.status != "draft":
            raise HTTPException(409, f"cannot approve a message in status '{m.status}'")
        m.status, m.approved_by = "approved", user.username
    elif action == "reject":
        m.status = "rejected"
        if m.followup_id and (f := s.get(M.FollowUp, m.followup_id)) and f.workflow_state == "reminder_drafted":
            f.workflow_state = "none"
    elif action == "send":
        if m.status != "approved":
            raise HTTPException(409, "a human must approve the message before it is sent")
        res = deliver(m.channel, m.recipient, m.body, m.subject, None, m.message_id)
        m.status = "sent" if res.ok else "failed"
        m.sent_at = datetime.now()
        m.delivery_detail = f"{res.provider}: {res.detail}"
        if res.ok and m.followup_id and (f := s.get(M.FollowUp, m.followup_id)):
            today = date.today()
            f.workflow_state = "reminder_sent"
            f.contact_attempts += 1
            f.last_contact_on = today
            f.first_contact_on = f.first_contact_on or today
            s.add(M.ContactEvent(followup_id=f.followup_id, at=datetime.now(), by_user=user.username,
                                 channel=m.channel, outcome="sent", note=res.detail[:300]))
    else:
        raise HTTPException(400, f"unknown action {action}")
    audit(s, user, f"message_{action}", target=message_id, decision=m.status, channel=m.channel)
    return _msg(m)


def log_contact(s: Session, user: UserCtx, followup_id: str, channel: str, outcome: str, note: str = "") -> dict:
    f = s.get(M.FollowUp, followup_id)
    if not f:
        raise HTTPException(404, "follow-up not found")
    today = date.today()
    s.add(M.ContactEvent(followup_id=followup_id, at=datetime.now(), by_user=user.username, channel=channel,
                         outcome=outcome, note=note[:400]))
    f.contact_attempts += 1
    f.last_contact_on = today
    f.first_contact_on = f.first_contact_on or today
    f.workflow_state = {"reached": "contacted", "scheduled": "scheduled", "unreachable": "unreachable",
                        "declined": "declined"}.get(outcome, outcome)
    audit(s, user, "contact_logged", target=followup_id, decision=outcome, channel=channel)
    return {"followup_id": followup_id, "workflow_state": f.workflow_state, "contact_attempts": f.contact_attempts}


def override(s: Session, user: UserCtx, followup_id: str, status: str, reason: str) -> dict:
    """Human override of a derived status (e.g. visit happened at another facility). Reason is mandatory."""
    if not reason.strip():
        raise HTTPException(400, "a reason is required for an override")
    f = s.get(M.FollowUp, followup_id)
    if not f:
        raise HTTPException(404, "follow-up not found")
    old = f.status
    f.status, f.override_reason = status, f"{reason} (by {user.username}, was '{old}')"
    if status == "completed" and not f.completed_on:
        f.completed_on = date.today()
    audit(s, user, "followup_override", target=followup_id, decision=status, previous=old, reason=reason)
    return {"followup_id": followup_id, "status": f.status, "override_reason": f.override_reason}


def _msg(m: M.OutboxMessage) -> dict:
    return {"message_id": m.message_id, "kind": m.kind, "followup_id": m.followup_id, "patient_id": m.patient_id,
            "recipient_type": m.recipient_type, "recipient": m.recipient, "channel": m.channel, "language": m.language,
            "body": m.body, "status": m.status, "created_by": m.created_by, "approved_by": m.approved_by,
            "created_at": m.created_at.isoformat() if m.created_at else None,
            "sent_at": m.sent_at.isoformat() if m.sent_at else None, "delivery_detail": m.delivery_detail}
