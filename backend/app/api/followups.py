"""Care coordination: follow-up queue, reminder drafts, approval-gated outbox, contacts, overrides."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ai.orchestrator import UserCtx
from backend.app.schemas.requests import BatchIn, ContactIn, DraftIn, MessageActionIn, OverrideIn
from backend.app.security import require_roles
from backend.app.services import followup_service as F
from common.settings import get_settings
from database.session import get_session

router = APIRouter(prefix="/api", tags=["coordination"])
staff = require_roles("doctor", "coordinator")


@router.get("/followups")
def get_queue(status: str = "due,overdue", followup_type: str = "", facility_id: str = "", q: str = "",
              user: UserCtx = Depends(staff), s: Session = Depends(get_session, scope="function")):
    statuses = [x for x in status.split(",") if x]
    return {"followups": F.queue(s, get_settings().reference_date, statuses, followup_type, facility_id, q)}


@router.get("/followups/summary")
def get_summary(user: UserCtx = Depends(staff), s: Session = Depends(get_session, scope="function")):
    return F.summary(s, get_settings().reference_date)


@router.post("/followups/drafts")
def drafts(body: DraftIn, user: UserCtx = Depends(staff), s: Session = Depends(get_session, scope="function")):
    return {"drafts": F.create_drafts(s, user, get_settings().reference_date, body.followup_ids, body.recipient,
                                      body.channel, body.language)}


@router.post("/followups/{followup_id}/contact")
def contact(followup_id: str, body: ContactIn, user: UserCtx = Depends(staff), s: Session = Depends(get_session, scope="function")):
    return F.log_contact(s, user, followup_id, body.channel, body.outcome, body.note)


@router.post("/followups/{followup_id}/override")
def override(followup_id: str, body: OverrideIn, user: UserCtx = Depends(staff), s: Session = Depends(get_session, scope="function")):
    return F.override(s, user, followup_id, body.status, body.reason)


@router.get("/outbox")
def outbox(status: str = "", kind: str = "", user: UserCtx = Depends(staff), s: Session = Depends(get_session, scope="function")):
    return {"messages": F.list_outbox(s, status, kind)}


@router.post("/outbox/approve-and-send")
def approve_and_send(body: BatchIn, user: UserCtx = Depends(staff), s: Session = Depends(get_session, scope="function")):
    """Batch convenience: the human's click IS the approval; each message is approved then sent."""
    out = []
    for mid in body.message_ids[:100]:
        F.act_on_message(s, user, mid, "approve")
        out.append(F.act_on_message(s, user, mid, "send"))
    return {"messages": out}


@router.post("/outbox/{message_id}")
def message_action(message_id: str, body: MessageActionIn, user: UserCtx = Depends(staff),
                   s: Session = Depends(get_session, scope="function")):
    return F.act_on_message(s, user, message_id, body.action, body.body)
