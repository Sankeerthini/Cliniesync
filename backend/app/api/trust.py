"""Trust Center: audit trail, guardrail statistics, safety playground, feedback."""
from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ai.llm.client import get_llm
from ai.orchestrator import UserCtx
from backend.app.schemas.requests import FeedbackIn, PlaygroundIn
from backend.app.security import current_user
from backend.app.services.audit import audit
from database.models import AIResponse, AuditLog, Feedback
from database.session import get_session
from guardrails.input_guard import InputGuard
from guardrails.nemo_adapter import get_nemo
from guardrails.policy import REFUSALS

router = APIRouter(prefix="/api/trust", tags=["trust"])


@router.get("/audit")
def audit_log(action: str = "", limit: int = 100, user: UserCtx = Depends(current_user), s: Session = Depends(get_session, scope="function")):
    stmt = select(AuditLog)
    if user.role != "admin":
        stmt = stmt.where(AuditLog.username == user.username)
    if action:
        stmt = stmt.where(AuditLog.action == action)
    rows = s.scalars(stmt.order_by(AuditLog.at.desc()).limit(min(limit, 500)))
    return {"entries": [{"at": r.at.isoformat(timespec="seconds"), "username": r.username, "role": r.role,
                         "action": r.action, "target": r.target, "decision": r.decision, "detail": r.detail} for r in rows]}


@router.get("/stats")
def stats(user: UserCtx = Depends(current_user), s: Session = Depends(get_session, scope="function")):
    by_status = dict(s.execute(select(AIResponse.status, func.count()).group_by(AIResponse.status)).all())
    blocked = dict(s.execute(select(AIResponse.intent, func.count()).where(AIResponse.status == "blocked")
                             .group_by(AIResponse.intent)).all())
    allowed = dict(s.execute(select(AIResponse.intent, func.count()).where(AIResponse.status != "blocked")
                             .group_by(AIResponse.intent)).all())
    fb = dict(s.execute(select(Feedback.kind, func.count()).group_by(Feedback.kind)).all())
    return {"by_status": by_status, "blocked_by_category": blocked, "allowed_by_intent": allowed, "feedback": fb}


@router.post("/playground")
def playground(body: PlaygroundIn, user: UserCtx = Depends(current_user), s: Session = Depends(get_session, scope="function")):
    """Run ONLY the input guard (no data access) so users can see why a request is allowed or blocked."""
    nemo = get_nemo()
    nemo.load(get_llm().available())
    d = InputGuard(nemo).check(body.text)
    audit(s, user, "safety_playground", decision="blocked" if not d.allowed else "allowed", category=d.category)
    return {"allowed": d.allowed, "intent": d.intent, "category": d.category, "layers": d.layers,
            "message": REFUSALS.get(d.category) if d.category else "Allowed - would be routed to " + d.intent}


@router.post("/feedback")
def feedback(body: FeedbackIn, user: UserCtx = Depends(current_user), s: Session = Depends(get_session, scope="function")):
    s.add(Feedback(at=datetime.now(), username=user.username, response_id=body.response_id, kind=body.kind,
                   note=body.note))
    audit(s, user, "feedback", target=body.response_id, decision=body.kind)
    return {"ok": True}
