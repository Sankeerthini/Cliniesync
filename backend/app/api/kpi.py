"""KPIs & pilot measurement."""
from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ai.orchestrator import UserCtx
from backend.app.schemas.requests import TimingIn
from backend.app.security import current_user
from backend.app.services import kpi_service
from backend.app.services.audit import audit
from database.models import BaselineTiming
from database.session import get_session

router = APIRouter(prefix="/api/kpi", tags=["kpi"])


@router.get("")
def kpis(user: UserCtx = Depends(current_user), s: Session = Depends(get_session, scope="function")):
    return kpi_service.compute(s)


@router.post("/timing")
def log_timing(body: TimingIn, user: UserCtx = Depends(current_user), s: Session = Depends(get_session, scope="function")):
    s.add(BaselineTiming(at=datetime.now(), username=user.username, task=body.task, method=body.method,
                         seconds=body.seconds))
    audit(s, user, "timing_logged", decision=body.method, task=body.task, seconds=body.seconds)
    return {"ok": True}
