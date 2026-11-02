"""Share Report (doctor only): preview in en/hi/bn/kn, then send via SMS / WhatsApp / e-mail.

`public` serves /r/<token>: the expiring link included in shared messages (no login; token is unguessable).
"""
from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from ai.orchestrator import UserCtx
from ai.translate.templates import LANGUAGES
from backend.app.schemas.requests import ReportIn, ShareIn
from backend.app.security import require_roles
from backend.app.services import report_service as R
from common.settings import get_settings
from database.models import Report
from database.session import get_session

router = APIRouter(prefix="/api/reports", tags=["reports"])
public = APIRouter(tags=["reports"])
doctor = require_roles("doctor")
_NO_INDEX = {"X-Robots-Tag": "noindex, nofollow", "Referrer-Policy": "no-referrer", "Cache-Control": "no-store"}


@router.get("/languages")
def languages():
    return {"languages": LANGUAGES}


@router.post("/preview")
def preview(body: ReportIn, user: UserCtx = Depends(doctor), s: Session = Depends(get_session, scope="function")):
    return R.build(s, body.response_id, body.language, user, get_settings().reference_date)


@router.post("/share")
def share(body: ShareIn, user: UserCtx = Depends(doctor), s: Session = Depends(get_session, scope="function")):
    return R.share(s, body.response_id, body.language, list(body.channels), body.recipient, body.consent_confirmed,
                   user, get_settings().reference_date, to_name=body.to_name, to_phone=body.to_phone,
                   to_email=body.to_email, base_url=body.base_url)


@router.get("")
def list_reports(patient_id: str = "", user: UserCtx = Depends(doctor), s: Session = Depends(get_session, scope="function")):
    stmt = select(Report).order_by(Report.created_at.desc()).limit(100)
    if patient_id:
        stmt = stmt.where(Report.patient_id == patient_id)
    return {"reports": [{"report_id": r.report_id, "created_at": r.created_at.isoformat(), "patient_id": r.patient_id,
                         "language": r.language, "channels": r.channels, "status": r.status, "created_by": r.created_by}
                        for r in s.scalars(stmt)]}


@router.get("/{report_id}/html")
def report_html(report_id: str, user: UserCtx = Depends(doctor), s: Session = Depends(get_session, scope="function")):
    r = s.get(Report, report_id)
    return {"html": r.html if r else ""}


@public.get("/r/{token}", response_class=HTMLResponse, include_in_schema=False)
def shared_report(token: str, s: Session = Depends(get_session, scope="function")):
    html = R.public_report(s, token)
    if html is None:
        return HTMLResponse("<!doctype html><meta charset='utf-8'><meta name='viewport' content='width=device-width'>"
                            "<body style='font-family:system-ui;max-width:560px;margin:40px auto;padding:0 16px'>"
                            "<h2>Link expired or not valid</h2><p>Please ask the clinic to share the report again.</p>",
                            status_code=404, headers=_NO_INDEX)
    return HTMLResponse(html, headers=_NO_INDEX)
