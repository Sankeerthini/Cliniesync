"""Operational KPIs + pilot measurement (Healthathon note 3: 'name one KPI, measure baseline and change').

PRIMARY KPI  - Follow-up (recall) completion rate:
    documented follow-ups completed <= 7 days after due date / follow-ups due in the window
SECONDARY    - ANC no-show rate, coordinator handoff lag (due -> first contact),
               time-to-information (manual chart review vs ClinieSync, time-motion log)
AI QUALITY   - verification / edit / rejection rates, latency
SAFETY       - blocked requests by category, 'wrong block' reports

Baseline = the 90 days before go-live; pilot = go-live -> reference date - 7 days (grace period).
The demo uses REFERENCE_DATE - PILOT_GO_LIVE_OFFSET_DAYS as go-live. On synthetic data no
intervention effect is simulated, so baseline and pilot are expected to be similar.
"""
from __future__ import annotations

import statistics
from datetime import date, timedelta

import pandas as pd
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from common.settings import get_settings
from database import models as M
from database.session import get_engine


def _recall(start: date, end: date, grace: int) -> dict:
    with get_engine().connect() as c:
        df = pd.read_sql(text("""SELECT due_on, due_month, status, completed_on FROM v_followups
                                 WHERE due_on BETWEEN :s AND :e AND status NOT IN ('cancelled','upcoming')"""),
                         c, params={"s": start.isoformat(), "e": end.isoformat()})
    if df.empty:
        return {"value": None, "n": 0, "window": [start.isoformat(), end.isoformat()], "series": []}
    on_time = (df["status"] == "completed") & ((pd.to_datetime(df["completed_on"]) - pd.to_datetime(df["due_on"]))
                                               .dt.days <= grace)
    df["on_time"] = on_time
    series = df.groupby("due_month").agg(n=("on_time", "size"), k=("on_time", "sum")).reset_index()
    series["value"] = (100 * series["k"] / series["n"]).round(1)
    return {"value": round(100 * on_time.mean(), 1), "n": int(len(df)), "window": [start.isoformat(), end.isoformat()],
            "series": series[["due_month", "value", "n"]].rename(columns={"due_month": "month"}).to_dict("records")}


def _no_show(start: date, end: date) -> dict:
    with get_engine().connect() as c:
        df = pd.read_sql(text("""SELECT status FROM v_visits WHERE facility_source='ehr_export' AND visit_category='ANC'
                                 AND visit_date BETWEEN :s AND :e"""), c,
                         params={"s": start.isoformat(), "e": end.isoformat()})
    n = len(df)
    return {"value": round(100 * (df["status"] == "no_show").mean(), 1) if n else None, "n": n,
            "window": [start.isoformat(), end.isoformat()]}


def compute(s: Session) -> dict:
    st = get_settings()
    ref = st.reference_date
    grace = st.followup_grace_days
    go_live = ref - timedelta(days=st.pilot_go_live_offset_days)
    b_start, b_end = go_live - timedelta(days=90), go_live - timedelta(days=1)
    p_start, p_end = go_live, ref - timedelta(days=grace)

    rb, rp = _recall(b_start, b_end, grace), _recall(p_start, p_end, grace)
    full = _recall(ref - timedelta(days=365), p_end, grace)
    nb, np_ = _no_show(b_start, b_end), _no_show(p_start, ref)

    lags = [(f.first_contact_on - f.due_on).days for f in s.scalars(
        select(M.FollowUp).where(M.FollowUp.first_contact_on.is_not(None)))]
    timings = s.execute(select(M.BaselineTiming.method, M.BaselineTiming.task, M.BaselineTiming.seconds)).all()
    manual = [t.seconds for t in timings if t.method == "manual"]
    tool = [t.seconds for t in timings if t.method == "cliniesync"]
    resp = s.execute(select(M.AIResponse.status, M.AIResponse.latency_ms, M.AIResponse.review_seconds,
                            M.AIResponse.intent, M.AIResponse.llm_used)).all()
    answered = [r for r in resp if r.status in ("pending_review", "verified", "edited", "rejected")]
    reviewed = [r for r in answered if r.status in ("verified", "edited", "rejected")]
    blocked = [r for r in resp if r.status == "blocked"]
    by_cat: dict[str, int] = {}
    for r in blocked:
        by_cat[r.intent] = by_cat.get(r.intent, 0) + 1
    wrong_blocks = s.scalar(select(func.count()).select_from(M.Feedback).where(M.Feedback.kind == "wrong_block")) or 0
    msgs = dict(s.execute(select(M.OutboxMessage.status, func.count()).group_by(M.OutboxMessage.status)).all())
    review_secs = [r.review_seconds for r in reviewed if r.review_seconds is not None]

    def pct(a, b):
        return round(100 * a / b, 1) if b else None

    return {
        "reference_date": ref.isoformat(), "go_live": go_live.isoformat(),
        "primary": {
            "name": "Follow-up (recall) completion rate", "unit": "%", "direction": "up",
            "definition": f"Documented follow-ups completed within {grace} days of the due date ÷ follow-ups due in the "
                          "window (cancelled excluded).",
            "baseline": rb, "pilot": rp,
            "delta_pp": round(rp["value"] - rb["value"], 1) if rb["value"] is not None and rp["value"] is not None else None,
            "target": "+10 percentage points within 90 days of go-live",
            "series": full["series"],
            "data_note": "Synthetic data: no intervention effect is simulated, so baseline ≈ pilot is expected. "
                         "In a real pilot the same query runs on live clinic data.",
        },
        "secondary": [
            {"name": "ANC no-show rate", "unit": "%", "direction": "down", "baseline": nb, "pilot": np_,
             "definition": "No-show ANC encounters ÷ booked ANC encounters (EHR facilities)."},
            {"name": "Handoff lag (due → first contact)", "unit": "days", "direction": "down",
             "value": statistics.median(lags) if lags else None, "n": len(lags),
             "definition": "Median days between a follow-up's due date and the coordinator's first logged contact. "
                           "Accrues from coordinator activity in ClinieSync."},
            {"name": "Time-to-information", "unit": "seconds", "direction": "down",
             "manual": round(statistics.median(manual), 1) if manual else None, "manual_n": len(manual),
             "cliniesync": round(statistics.median(tool), 1) if tool else None, "cliniesync_n": len(tool),
             "system_latency_ms": round(statistics.median([r.latency_ms for r in answered])) if answered else None,
             "definition": "Time-motion study: seconds to answer a standard question by manual chart review vs with "
                           "ClinieSync (incl. human verification). Log timings on this page."},
        ],
        "ai_quality": {
            "answers": len(answered), "reviewed": len(reviewed),
            "verified_pct": pct(sum(r.status == "verified" for r in reviewed), len(reviewed)),
            "edited_pct": pct(sum(r.status == "edited" for r in reviewed), len(reviewed)),
            "rejected_pct": pct(sum(r.status == "rejected" for r in reviewed), len(reviewed)),
            "median_review_seconds": statistics.median(review_secs) if review_secs else None,
            "llm_share_pct": pct(sum(bool(r.llm_used) for r in answered), len(answered)),
        },
        "safety": {"blocked_total": len(blocked), "blocked_by_category": by_cat, "wrong_block_reports": wrong_blocks,
                   "block_rate_pct": pct(len(blocked), len(resp))},
        "reminders": msgs,
    }
