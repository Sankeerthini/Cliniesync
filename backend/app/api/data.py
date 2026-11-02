"""Data Hub: data-quality report, sources, register upload preview, ETL re-run (admin)."""
import json
import tempfile
import threading
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from ai.orchestrator import UserCtx
from backend.app.security import require_roles
from backend.app.services.audit import audit
from common.settings import get_settings
from database.models import EtlRun
from database.session import get_session

router = APIRouter(prefix="/api/data", tags=["data"])
admin = require_roles("admin")
_etl_state = {"running": False, "last_error": None, "last_finished": None}


@router.get("/quality")
def quality(user: UserCtx = Depends(require_roles("admin", "doctor", "coordinator")), s: Session = Depends(get_session, scope="function")):
    run = s.scalars(select(EtlRun).order_by(EtlRun.at.desc())).first()
    manifest_path = get_settings().raw_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else None
    return {"report": run.report if run else None, "manifest": manifest, "etl": _etl_state}


@router.post("/register/preview")
async def register_preview(file: UploadFile = File(...), user: UserCtx = Depends(admin)):
    """Validate an uploaded Excel ANC register without loading it (shows what the ETL would do)."""
    if not (file.filename or "").lower().endswith((".xlsx", ".xls")):
        raise HTTPException(400, "please upload an Excel register (.xlsx)")
    from etl.extract import Staging, extract_excel_register
    from etl.clean import parse_date

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / Path(file.filename).name
        path.write_bytes(await file.read())
        st = Staging()
        try:
            extract_excel_register(path, "UPLOAD", "Uploaded facility", st)
        except Exception as exc:
            raise HTTPException(422, f"could not read the register: {exc}") from exc
    enc, pats = st.get("encounters"), st.get("patients")
    bad_dates = int(sum(parse_date(v) is None for v in enc["date"])) if len(enc) else 0
    return {"file": file.filename, "stats": st.source_stats,
            "checks": {"rows": len(pats), "encounters": len(enc), "unparseable_dates": bad_dates,
                       "missing_rch_id": int((pats["rch_id"] == "").sum()) if len(pats) else 0},
            "sample": enc.head(8).astype(str).to_dict("records")}


@router.post("/etl/run")
def run_etl(user: UserCtx = Depends(admin), s: Session = Depends(get_session, scope="function")):
    if _etl_state["running"]:
        raise HTTPException(409, "ETL is already running")

    def job():
        from etl.pipeline import run

        _etl_state.update(running=True, last_error=None)
        try:
            run()
        except Exception as exc:  # pragma: no cover
            _etl_state["last_error"] = str(exc)
        finally:
            from datetime import datetime

            _etl_state.update(running=False, last_finished=datetime.now().isoformat(timespec="seconds"))

    threading.Thread(target=job, daemon=True).start()
    audit(s, user, "etl_run", decision="started")
    return {"started": True}

