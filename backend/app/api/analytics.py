"""Population analytics dashboard (governed SQL metrics; de-identified)."""
from datetime import date

from fastapi import APIRouter, Depends, HTTPException

from ai.orchestrator import UserCtx
from ai.sql import semantic_layer as SL
from backend.app.security import current_user
from common.settings import get_settings

router = APIRouter(prefix="/api/analytics", tags=["analytics"])
DASHBOARD = ["visit_volume", "anc_dropoff", "followup_completion", "no_show_trend", "investigation_utilization",
             "visit_frequency", "registration_timeliness", "pnc_coverage", "immunization_coverage", "facility_comparison"]


def _params(start: str, end: str, facility_id: str) -> SL.Params:
    return SL.Params(ref=get_settings().reference_date, start=date.fromisoformat(start) if start else None,
                     end=date.fromisoformat(end) if end else None, facility_id=facility_id or None)


@router.get("/metrics")
def metrics(user: UserCtx = Depends(current_user)):
    return {"metrics": SL.available_metrics(), "dashboard": DASHBOARD}


@router.get("/dashboard")
def dashboard(facility_id: str = "", user: UserCtx = Depends(current_user)):
    p = _params("", "", facility_id)
    return {"reference_date": p.ref.isoformat(), "facility_id": facility_id or None,
            "metrics": {m: SL.run(m, p) for m in DASHBOARD}}


@router.get("/{metric_id}")
def metric(metric_id: str, start: str = "", end: str = "", facility_id: str = "", user: UserCtx = Depends(current_user)):
    if metric_id not in SL.CATALOGUE:
        raise HTTPException(404, "unknown metric")
    return SL.run(metric_id, _params(start, end, facility_id))
