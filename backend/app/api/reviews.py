"""Human verification of AI answers (verify / edit / reject) - the 'human in control' loop."""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ai.orchestrator import UserCtx
from backend.app.schemas.requests import ReviewIn
from backend.app.security import current_user
from backend.app.services.audit import audit
from database.models import AIResponse
from database.session import get_session
from guardrails.output_guard import check as output_check

router = APIRouter(prefix="/api/reviews", tags=["reviews"])


def _row(r: AIResponse, full: bool = False) -> dict:
    d = {"response_id": r.response_id, "created_at": r.created_at.isoformat(), "query": r.query_text,
         "intent": r.intent, "route": r.route, "patient_id": r.patient_id, "status": r.status,
         "llm_used": r.llm_used, "latency_ms": r.latency_ms, "reviewed_by": r.reviewed_by,
         "reviewed_at": r.reviewed_at.isoformat() if r.reviewed_at else None, "review_note": r.review_note,
         "answer": r.final_text or r.answer_text, "input_mode": r.input_mode}
    if full:
        d["payload"] = r.payload
        d["original_answer"] = r.answer_text
    return d


@router.get("")
def list_reviews(status: str = "pending_review", user: UserCtx = Depends(current_user), s: Session = Depends(get_session, scope="function")):
    stmt = select(AIResponse).where(AIResponse.username == user.username)
    if status != "all":
        stmt = stmt.where(AIResponse.status.in_(status.split(",")))
    else:
        stmt = stmt.where(AIResponse.status.in_(["pending_review", "verified", "edited", "rejected"]))
    return {"responses": [_row(r) for r in s.scalars(stmt.order_by(AIResponse.created_at.desc()).limit(200))]}


@router.get("/{response_id}")
def get_review(response_id: str, user: UserCtx = Depends(current_user), s: Session = Depends(get_session, scope="function")):
    r = s.get(AIResponse, response_id)
    if not r or r.username != user.username:
        raise HTTPException(404, "response not found")
    return _row(r, full=True)


@router.post("/{response_id}")
def review(response_id: str, body: ReviewIn, user: UserCtx = Depends(current_user), s: Session = Depends(get_session, scope="function")):
    r = s.get(AIResponse, response_id)
    if not r or r.username != user.username:
        raise HTTPException(404, "response not found")
    if r.status not in ("pending_review", "verified", "edited"):
        raise HTTPException(409, f"cannot review a response in status '{r.status}'")
    if body.action == "edit":
        if not body.edited_text or not body.edited_text.strip():
            raise HTTPException(400, "edited_text is required")
        # Human edits are checked too - an edited answer must not introduce clinical advice into a shareable report.
        od = output_check(body.edited_text, evidence_text="", evidence_ids=set(), role=user.role, generated_by="human")
        if any(c["check"].startswith("O1") and c["verdict"] == "fail" for c in od.checks):
            raise HTTPException(422, {"message": "The edit contains diagnostic/treatment/risk language. "
                                                 "Clinical instructions belong in the prescription/EHR, not in a "
                                                 "ClinieSync summary.", "checks": od.checks})
        r.final_text, r.status = body.edited_text.strip(), "edited"
    elif body.action == "verify":
        r.final_text, r.status = r.final_text or r.answer_text, "verified"
    else:
        r.status = "rejected"
    r.reviewed_by, r.reviewed_at = user.username, datetime.now()
    r.review_seconds = int((r.reviewed_at - r.created_at).total_seconds())
    r.review_note = body.note
    audit(s, user, f"review_{body.action}", target=response_id, decision=r.status, note=body.note)
    return _row(r)
