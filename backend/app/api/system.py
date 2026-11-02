"""Health, home overview and responsible-AI policy endpoints."""
from datetime import timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ai.llm.client import get_llm
from ai.orchestrator import UserCtx
from ai.rag.vector_store import get_vector_store
from ai.voice import stt
from backend.app.security import current_user
from backend.app.services.notify.providers import delivery_status
from common.settings import get_settings
from database import models as M
from database.session import get_session
from guardrails.nemo_adapter import get_nemo
from guardrails.policy import INTENT_MATRIX, POLICY_VERSION, ROLE_INTENTS, ROLE_SCOPES, SUGGESTIONS

router = APIRouter(prefix="/api", tags=["system"])


@router.get("/health")
def health(s: Session = Depends(get_session, scope="function")):
    st = get_settings()
    llm = get_llm()
    ok = llm.available()
    nemo = get_nemo()
    nemo.load(ok)
    try:
        vs = get_vector_store()
        vector = {"backend": vs.name, "chunks": vs.count()}
    except Exception as exc:  # pragma: no cover
        vector = {"backend": "error", "detail": str(exc)}
    return {"status": "ok", "reference_date": st.reference_date.isoformat(),
            "database": {"url": st.database_url.split("///")[0] + "///…", "patients": s.scalar(select(func.count()).select_from(M.Patient))},
            "llm": {"available": ok, "model": st.llm_model, "endpoint": st.llm_base_url,
                    "mode": "open-source LLM" if ok else "deterministic fallback (LLM offline)"},
            "guardrails": nemo.describe(), "vector_store": vector, "voice": {"server_stt": stt.available(),
                                                                            "browser_stt": "Web Speech API (en-IN)"},
            "delivery": delivery_status()}


@router.get("/policy")
def policy(user: UserCtx = Depends(current_user)):
    return {"version": POLICY_VERSION, "intent_matrix": INTENT_MATRIX,
            "roles": {r: {"intents": sorted(ROLE_INTENTS[r]), "scopes": sorted(ROLE_SCOPES[r])} for r in ROLE_INTENTS},
            "suggestions": SUGGESTIONS}


@router.get("/overview")
def overview(user: UserCtx = Depends(current_user), s: Session = Depends(get_session, scope="function")):
    ref = get_settings().reference_date
    month_start = ref.replace(day=1)
    cnt = lambda stmt: s.scalar(stmt) or 0  # noqa: E731
    visits_month = cnt(select(func.count()).select_from(M.Visit).where(M.Visit.status == "completed",
                                                                         M.Visit.visit_date >= month_start))
    my_pending = cnt(select(func.count()).select_from(M.AIResponse).where(M.AIResponse.username == user.username,
                                                                           M.AIResponse.status == "pending_review"))
    tiles = []
    if user.role == "doctor":
        tiles = [
            {"label": "Active antenatal patients", "value": cnt(select(func.count()).select_from(M.Pregnancy)
                                                               .where(M.Pregnancy.status == "antenatal"))},
            {"label": "Visits this month", "value": visits_month},
            {"label": "Results awaited > 7 days", "value": cnt(select(func.count()).select_from(M.Investigation).where(
                M.Investigation.status == "pending", M.Investigation.ordered_on < ref - timedelta(days=7)))},
            {"label": "Answers awaiting your review", "value": my_pending},
        ]
    elif user.role == "coordinator":
        fu = dict(s.execute(select(M.FollowUp.status, func.count()).group_by(M.FollowUp.status)).all())
        tiles = [
            {"label": "Due in next 7 days", "value": fu.get("due", 0)},
            {"label": "Overdue (≤ 28 days)", "value": fu.get("overdue", 0)},
            {"label": "Reminders awaiting approval", "value": cnt(select(func.count()).select_from(M.OutboxMessage)
                                                                  .where(M.OutboxMessage.status == "draft"))},
            {"label": "Answers awaiting your review", "value": my_pending},
        ]
    else:
        from ai.sql import semantic_layer as SL

        drop = SL.run("anc_dropoff", SL.Params(ref=ref))
        recall = SL.run("followup_completion", SL.Params(ref=ref, start=ref - timedelta(days=97)))
        anc4 = next((r["pct"] for r in (drop["table"] or {}).get("rows", []) if r["stage"] == "ANC4+"), None)
        tiles = [
            {"label": "MCH visits this month", "value": visits_month},
            {"label": "ANC4+ completion (12 mo)", "value": anc4, "unit": "%"},
            {"label": "Follow-ups completed on time (90 d)", "value": _first_pct(recall), "unit": "%"},
            {"label": "Requests blocked by guardrails", "value": cnt(select(func.count()).select_from(M.AIResponse)
                                                                     .where(M.AIResponse.status == "blocked"))},
        ]
    return {"role": user.role, "display_name": user.display_name, "reference_date": ref.isoformat(), "tiles": tiles,
            "suggestions": SUGGESTIONS.get(user.role, [])}


def _first_pct(result: dict):
    import re

    m = re.match(r"([\d.]+)%", result.get("narrative", ""))
    return float(m.group(1)) if m else None
