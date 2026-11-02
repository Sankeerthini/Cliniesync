"""LOAD: write the unified layer into the SQL database.

Only clinical tables are rebuilt; application tables (users, reviews, audit
log, outbox...) are preserved. Human workflow state on follow-ups (contact
attempts, overrides) is carried over across re-loads.
"""
from __future__ import annotations

import math
from datetime import date, datetime

import pandas as pd
from sqlalchemy import select, text

from database import models as M
from database.session import create_views, get_engine, init_db
from database.views import ANALYTICS_VIEWS

CLINICAL_MODELS = [M.Facility, M.Provider, M.Patient, M.PatientIdentifier, M.Pregnancy, M.Child, M.Visit,
                   M.Observation, M.Investigation, M.Immunization, M.FollowUp, M.Document]
_WORKFLOW_FIELDS = ["workflow_state", "contact_attempts", "last_contact_on", "first_contact_on", "assigned_to",
                    "override_reason"]


def _clean(v):
    if v is None:
        return None
    if isinstance(v, float) and math.isnan(v):
        return None
    if isinstance(v, pd.Timestamp):
        return None if pd.isna(v) else v.date()
    if v is pd.NaT:
        return None
    if hasattr(v, "item") and not isinstance(v, (date, datetime, str)):
        return v.item()  # numpy scalar -> python
    return v


def _records(model, df: pd.DataFrame) -> list[dict]:
    cols = [c.name for c in model.__table__.columns]
    out = []
    for r in df.to_dict("records"):
        out.append({c: _clean(r.get(c)) for c in cols if c in r})
    return out


def _saved_workflow() -> dict:
    eng = get_engine()
    try:
        with eng.connect() as conn:
            rows = conn.execute(select(M.FollowUp.__table__)).mappings().all()
    except Exception:
        return {}
    return {(r["patient_id"], r["followup_type"], r["due_on"]): {k: r[k] for k in _WORKFLOW_FIELDS}
            for r in rows if r["workflow_state"] != "none" or r["override_reason"]}


def load(frames: dict[str, pd.DataFrame]) -> dict:
    saved = _saved_workflow()
    eng = get_engine()
    with eng.begin() as conn:
        for v in ANALYTICS_VIEWS:
            conn.execute(text(f"DROP VIEW IF EXISTS {v}"))
    M.Base.metadata.drop_all(eng, tables=[m.__table__ for m in CLINICAL_MODELS])
    init_db()
    counts = {}
    fu = frames.get("followups")
    if fu is not None and saved:
        for i, r in fu.iterrows():
            k = (r["patient_id"], r["followup_type"], r["due_on"])
            if k in saved:
                for f, val in saved[k].items():
                    fu.at[i, f] = val
    with eng.begin() as conn:
        for model in CLINICAL_MODELS:
            df = frames.get(model.__tablename__)
            if df is None or df.empty:
                counts[model.__tablename__] = 0
                continue
            recs = _records(model, df)
            for i in range(0, len(recs), 2000):
                conn.execute(model.__table__.insert(), recs[i:i + 2000])
            counts[model.__tablename__] = len(recs)
    create_views()
    return {"rows_loaded": counts, "workflow_states_preserved": len(saved)}
