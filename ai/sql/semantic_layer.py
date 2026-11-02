"""Semantic layer: governed, pre-defined operational metrics (the SQL analytics engine).

Why a semantic layer instead of letting the LLM write all SQL?
  * definitions (numerators, denominators, cohorts) are reviewed once and reused
  * cohort choices avoid classic biases - e.g. ANC drop-off is computed only for
    pregnancies whose EDD has passed (otherwise recent registrants look like drop-outs)
  * the generated SQL is shown to the user for transparency
LLM text-to-SQL (ai/sql/text_to_sql.py) is only a fallback for questions no metric covers.

All metrics are OPERATIONAL (volumes, completion, timeliness) - none estimates clinical risk.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, timedelta

import pandas as pd
from sqlalchemy import text

from database.session import get_engine

CATEGORY_ORDER = ["ANC", "Delivery", "PNC", "Child"]
CATEGORY_LABEL = {"ANC": "Antenatal (ANC)", "Delivery": "Delivery", "PNC": "Postnatal (PNC)", "Child": "Child / immunization"}


@dataclass
class Params:
    ref: date
    start: date | None = None
    end: date | None = None
    period_label: str | None = None
    facility_id: str | None = None


def _q(sql: str, params: dict) -> pd.DataFrame:
    with get_engine().connect() as conn:
        return pd.read_sql(text(sql), conn, params=params)


def _fac(p: Params, alias: str = "") -> tuple[str, dict]:
    if p.facility_id:
        return f" AND {alias}facility_id = :facility_id", {"facility_id": p.facility_id}
    return "", {}


def _months_back(ref: date, n: int) -> date:
    y, m = ref.year, ref.month - n
    while m <= 0:
        m += 12
        y -= 1
    return date(y, m, 1)


def _pct(a, b) -> float | None:
    return round(100 * a / b, 1) if b else None


def _result(metric, title, sql, narrative, charts=None, table=None, caveats=None, stats=None, definition=None):
    return {"metric": metric, "title": title, "sql": re.sub(r"\s+", " ", sql).strip(), "narrative": narrative,
            "charts": charts or [], "table": table, "caveats": caveats or [], "stats": stats or [],
            "definition": definition}


def _table(df: pd.DataFrame, labels: dict | None = None) -> dict:
    labels = labels or {}
    return {"columns": [{"key": c, "label": labels.get(c, c.replace("_", " ").capitalize())} for c in df.columns],
            "rows": df.astype(object).where(pd.notna(df), None).to_dict("records")}


# =============================================================================== metrics
def visit_volume(p: Params) -> dict:
    start = p.start or _months_back(p.ref, 11)
    end = p.end or p.ref
    f, fp = _fac(p)
    sql = f"""SELECT visit_month, visit_category, COUNT(*) AS visits FROM v_visits
              WHERE status = 'completed' AND visit_date BETWEEN :start AND :end{f}
              GROUP BY visit_month, visit_category ORDER BY visit_month"""
    df = _q(sql, {"start": start.isoformat(), "end": end.isoformat(), **fp})
    piv = df.pivot_table(index="visit_month", columns="visit_category", values="visits", fill_value=0).reset_index()
    for c in CATEGORY_ORDER:
        if c not in piv:
            piv[c] = 0
    piv = piv[["visit_month", *CATEGORY_ORDER]]
    total = int(df["visits"].sum())
    busiest = piv.assign(t=piv[CATEGORY_ORDER].sum(axis=1)).sort_values("t").iloc[-1] if len(piv) else None
    narrative = (f"{total:,} completed maternal & child health visits were documented between {start:%d %b %Y} and "
                 f"{end:%d %b %Y}" + (f"; the busiest month was {busiest['visit_month']} ({int(busiest['t'])} visits)."
                                      if busiest is not None else "."))
    chart = {"id": "visit_volume", "type": "stacked_bar", "title": "Completed visits per month",
             "subtitle": "By visit category", "x": "visit_month",
             "series": [{"key": c, "label": CATEGORY_LABEL[c]} for c in CATEGORY_ORDER],
             "data": piv.to_dict("records"), "value_format": "int"}
    return _result("visit_volume", "Visit volume", sql, narrative, [chart], _table(piv),
                   ["The current month is partial (up to the reference date)."])


def visit_count(p: Params) -> dict:
    start = p.start or p.ref.replace(day=1)
    end = p.end or p.ref
    span = (end - start).days + 1
    pstart, pend = start - timedelta(days=span), start - timedelta(days=1)
    f, fp = _fac(p)
    sql = f"""SELECT visit_category, COUNT(*) AS visits FROM v_visits
              WHERE status = 'completed' AND visit_date BETWEEN :start AND :end{f} GROUP BY visit_category"""
    cur = _q(sql, {"start": start.isoformat(), "end": end.isoformat(), **fp}).set_index("visit_category")["visits"]
    prev = _q(sql, {"start": pstart.isoformat(), "end": pend.isoformat(), **fp}).set_index("visit_category")["visits"]
    total, ptotal = int(cur.sum()), int(prev.sum())
    stats = [{"label": "All MCH visits", "value": total, "delta": total - ptotal, "delta_label": "vs previous period"}]
    stats += [{"label": CATEGORY_LABEL[c], "value": int(cur.get(c, 0)), "delta": int(cur.get(c, 0)) - int(prev.get(c, 0)),
               "delta_label": "vs previous period"} for c in CATEGORY_ORDER]
    label = p.period_label or f"{start:%d %b} - {end:%d %b %Y}"
    parts = ", ".join(f"{int(cur.get(c, 0))} {CATEGORY_LABEL[c]}" for c in CATEGORY_ORDER)
    narrative = f"{total} maternal and child healthcare visits were completed in {label} ({parts}). " \
                f"Previous period of equal length: {ptotal}."
    chart = {"id": "visit_count", "type": "bar", "title": f"Completed visits - {label}", "x": "category",
             "series": [{"key": "visits", "label": "Visits"}],
             "data": [{"category": CATEGORY_LABEL[c], "visits": int(cur.get(c, 0))} for c in CATEGORY_ORDER],
             "value_format": "int"}
    return _result("visit_count", f"MCH visits - {label}", sql, narrative, [chart], stats=stats)


def anc_dropoff(p: Params) -> dict:
    """ANC continuation funnel + drop-off trend for pregnancies whose antenatal window is complete."""
    start = p.start or (p.ref - timedelta(days=365))
    f, fp = _fac(p)
    sql = f"""SELECT edd, anc_visits_completed FROM v_pregnancies
              WHERE edd < :ref AND edd >= :start AND registration_date IS NOT NULL{f}"""
    df = _q(sql, {"ref": p.ref.isoformat(), "start": start.isoformat(), **fp})
    df["edd_month"] = df["edd"].astype(str).str[:7]
    n = len(df)
    funnel = [{"stage": f"ANC{k}{'+' if k == 4 else ''}", "pregnancies": int((df["anc_visits_completed"] >= k).sum()),
               "pct": _pct((df["anc_visits_completed"] >= k).sum(), n)} for k in range(1, 5)]
    trend = []
    for m, g in df.groupby("edd_month"):   # EDD cohorts: everyone had the full antenatal window
        if len(g) >= 5:
            reached = _pct((g["anc_visits_completed"] >= 4).sum(), len(g))
            trend.append({"edd_month": m, "dropoff_pct": round(100 - reached, 1), "n": len(g)})
    anc4 = funnel[3]["pct"] if n else None
    narrative = (f"Of {n} pregnancies whose EDD fell between {start:%b %Y} and {p.ref:%b %Y}, {anc4}% completed 4 or "
                 f"more documented ANC contacts; {round(100 - anc4, 1) if anc4 is not None else '-'}% dropped off "
                 f"before ANC4.") if n else "No pregnancies with a completed antenatal window in this period."
    charts = [
        {"id": "anc_funnel", "type": "funnel", "title": "ANC continuation", "subtitle":
            f"Share of {n} pregnancies reaching each contact", "x": "stage",
         "series": [{"key": "pct", "label": "% of cohort"}], "data": funnel, "value_format": "pct"},
        {"id": "anc_dropoff_trend", "type": "line", "title": "Drop-off before ANC4", "subtitle":
            "By EDD month (cohorts with n ≥ 5)", "x": "edd_month",
         "series": [{"key": "dropoff_pct", "label": "Drop-off %"}], "data": trend, "value_format": "pct"},
    ]
    return _result("anc_dropoff", "ANC drop-off", sql, narrative, charts, _table(pd.DataFrame(funnel)),
                   ["Cohort = pregnancies whose EDD has passed, so every woman had the full antenatal window "
                    "(avoids counting recent registrants as drop-outs).",
                    "Late registrants have fewer opportunities for 4 contacts; contacts at other facilities are "
                    "not visible unless linked."],
                   definition="Drop-off = 100% − share of the cohort with ≥ 4 documented ANC contacts.")


def no_show_trend(p: Params) -> dict:
    start = p.start or _months_back(p.ref, 11)
    f, fp = _fac(p)
    sql = f"""SELECT visit_month, status, COUNT(*) AS n FROM v_visits
              WHERE facility_source = 'ehr_export' AND visit_category = 'ANC'
              AND visit_date BETWEEN :start AND :end{f} GROUP BY visit_month, status ORDER BY visit_month"""
    df = _q(sql, {"start": start.isoformat(), "end": (p.end or p.ref).isoformat(), **fp})
    piv = df.pivot_table(index="visit_month", columns="status", values="n", fill_value=0).reset_index()
    for c in ("completed", "no_show"):
        if c not in piv:
            piv[c] = 0
    piv["booked"] = piv["completed"] + piv["no_show"]
    piv["no_show_pct"] = (100 * piv["no_show"] / piv["booked"]).round(1)
    overall = _pct(piv["no_show"].sum(), piv["booked"].sum())
    narrative = f"ANC no-show rate over the period: {overall}% ({int(piv['no_show'].sum())} of " \
                f"{int(piv['booked'].sum())} booked ANC appointments)."
    chart = {"id": "no_show", "type": "line", "title": "ANC no-show rate", "subtitle": "Monthly, EHR facilities",
             "x": "visit_month", "series": [{"key": "no_show_pct", "label": "No-show %"}],
             "data": piv[["visit_month", "no_show_pct", "booked"]].to_dict("records"), "value_format": "pct"}
    return _result("no_show_trend", "No-show trend", sql, narrative, [chart],
                   _table(piv[["visit_month", "booked", "completed", "no_show", "no_show_pct"]]),
                   ["Paper/Excel registers do not record no-shows, so register-only facilities are excluded."],
                   definition="No-show % = no-show ANC encounters ÷ (completed + no-show) ANC encounters.")


def investigation_utilization(p: Params) -> dict:
    start = p.start or (p.ref - timedelta(days=180))
    f, fp = _fac(p)
    sql = f"""SELECT test_name, category, status, turnaround_days FROM v_investigations
              WHERE ordered_on BETWEEN :start AND :end{f}"""
    df = _q(sql, {"start": start.isoformat(), "end": (p.end or p.ref).isoformat(), **fp})
    g = df.groupby("test_name")
    out = pd.DataFrame({
        "ordered": g.size(),
        "resulted": g.apply(lambda x: int((x["status"] == "resulted").sum()), include_groups=False),
        "pending": g.apply(lambda x: int((x["status"] == "pending").sum()), include_groups=False),
        "median_turnaround_days": g["turnaround_days"].median().round(1),
    }).reset_index().sort_values("ordered", ascending=False)
    out["completion_pct"] = (100 * out["resulted"] / out["ordered"]).round(1)
    total, pending = int(out["ordered"].sum()), int(out["pending"].sum())
    narrative = (f"{total:,} investigations were ordered since {start:%d %b %Y}; {pending} "
                 f"({_pct(pending, total)}%) have no documented result yet. Median turnaround: "
                 f"{df['turnaround_days'].median():.0f} day(s) overall.") if total else "No investigations in this period."
    chart = {"id": "investigations", "type": "stacked_hbar", "title": "Investigations ordered",
             "subtitle": "Resulted vs awaiting result", "x": "test_name",
             "series": [{"key": "resulted", "label": "Resulted"}, {"key": "pending", "label": "Awaiting result"}],
             "data": out[["test_name", "resulted", "pending"]].to_dict("records"), "value_format": "int"}
    tat = {"id": "turnaround", "type": "hbar", "title": "Median turnaround (days)", "x": "test_name",
           "series": [{"key": "median_turnaround_days", "label": "Median days"}],
           "data": out[["test_name", "median_turnaround_days"]].dropna().to_dict("records"), "value_format": "num"}
    return _result("investigation_utilization", "Investigation utilization", sql, narrative, [chart, tat], _table(out),
                   ["'Awaiting result' includes orders placed in the last few days."])


def visit_frequency(p: Params) -> dict:
    start = p.start or (p.ref - timedelta(days=365))
    f, fp = _fac(p)
    sql = f"""SELECT anc_visits_completed FROM v_pregnancies
              WHERE edd < :ref AND edd >= :start AND registration_date IS NOT NULL{f}"""
    df = _q(sql, {"ref": p.ref.isoformat(), "start": start.isoformat(), **fp})
    counts = df["anc_visits_completed"].clip(upper=5).value_counts().reindex(range(0, 6), fill_value=0)
    data = [{"anc_contacts": ("5+" if k == 5 else str(k)), "pregnancies": int(v)} for k, v in counts.items()]
    mean = df["anc_visits_completed"].mean() if len(df) else 0
    narrative = f"Across {len(df)} pregnancies with a completed antenatal window, the mean number of documented ANC " \
                f"contacts was {mean:.1f} (median {df['anc_visits_completed'].median() if len(df) else 0:.0f})."
    chart = {"id": "visit_frequency", "type": "bar", "title": "ANC contacts per pregnancy", "x": "anc_contacts",
             "series": [{"key": "pregnancies", "label": "Pregnancies"}], "data": data, "value_format": "int"}
    return _result("visit_frequency", "Visit frequency", sql, narrative, [chart], _table(pd.DataFrame(data)))


def registration_timeliness(p: Params) -> dict:
    start = p.start or _months_back(p.ref, 11)
    f, fp = _fac(p)
    sql = f"""SELECT registration_month, registration_ga_weeks FROM v_pregnancies
              WHERE registration_date BETWEEN :start AND :end{f}"""
    df = _q(sql, {"start": start.isoformat(), "end": (p.end or p.ref).isoformat(), **fp})
    trend = [{"registration_month": m, "first_trimester_pct": _pct((g["registration_ga_weeks"] <= 12).sum(), len(g)),
              "n": len(g)} for m, g in df.groupby("registration_month")]
    overall = _pct((df["registration_ga_weeks"] <= 12).sum(), len(df))
    narrative = f"{overall}% of {len(df)} pregnancies were registered within the first trimester (≤ 12 weeks)."
    chart = {"id": "registration", "type": "line", "title": "First-trimester registration", "x": "registration_month",
             "series": [{"key": "first_trimester_pct", "label": "% registered ≤ 12 w"}], "data": trend,
             "value_format": "pct"}
    return _result("registration_timeliness", "Early registration", sql, narrative, [chart], _table(pd.DataFrame(trend)))


def immunization_coverage(p: Params) -> dict:
    f, fp = _fac(p)
    sql = f"""SELECT schedule_label, child_key, MIN(CASE WHEN given_on IS NOT NULL THEN 1 ELSE 0 END) AS given
              FROM v_immunizations WHERE due_on <= :ref{f} GROUP BY schedule_label, child_key"""
    df = _q(sql, {"ref": p.ref.isoformat(), **fp})
    order = ["Birth", "6 weeks", "10 weeks", "14 weeks", "9 months"]
    data = []
    for s in order:
        g = df[df["schedule_label"] == s]
        if len(g):
            data.append({"session": s, "coverage_pct": _pct(g["given"].sum(), len(g)), "due": len(g),
                         "given": int(g["given"].sum())})
    narrative = "Session coverage among children who have reached each due date: " + \
                "; ".join(f"{d['session']} {d['coverage_pct']}%" for d in data) + "."
    chart = {"id": "immunization", "type": "bar", "title": "Immunization session coverage", "x": "session",
             "series": [{"key": "coverage_pct", "label": "% of due children vaccinated"}], "data": data,
             "value_format": "pct"}
    return _result("immunization_coverage", "Immunization coverage", sql, narrative, [chart], _table(pd.DataFrame(data)),
                   ["Children are tracked only at facilities with an EHR export."])


def followup_completion(p: Params, grace_days: int = 7) -> dict:
    start = p.start or _months_back(p.ref, 5)
    end = min(p.end or p.ref, p.ref - timedelta(days=grace_days))
    f, fp = _fac(p)
    sql = f"""SELECT due_month, followup_type, status, due_on, completed_on FROM v_followups
              WHERE due_on BETWEEN :start AND :end AND status NOT IN ('cancelled', 'upcoming'){f}"""
    df = _q(sql, {"start": start.isoformat(), "end": end.isoformat(), **fp})
    if df.empty:
        return _result("followup_completion", "Follow-up completion", sql, "No follow-ups due in this period.")
    due = pd.to_datetime(df["due_on"])
    comp = pd.to_datetime(df["completed_on"])
    df["on_time"] = (df["status"] == "completed") & ((comp - due).dt.days <= grace_days)
    trend = df.groupby("due_month").agg(due=("on_time", "size"), on_time=("on_time", "sum")).reset_index()
    trend["on_time_pct"] = (100 * trend["on_time"] / trend["due"]).round(1)
    by_type = df.groupby("followup_type").agg(due=("on_time", "size"), on_time=("on_time", "sum")).reset_index()
    by_type["on_time_pct"] = (100 * by_type["on_time"] / by_type["due"]).round(1)
    overall = _pct(df["on_time"].sum(), len(df))
    narrative = f"{overall}% of {len(df)} documented follow-ups due between {start:%d %b %Y} and {end:%d %b %Y} " \
                f"were completed within {grace_days} days of the due date."
    charts = [
        {"id": "recall_trend", "type": "line", "title": "Follow-up completion on time", "x": "due_month",
         "series": [{"key": "on_time_pct", "label": "% completed ≤ 7 days after due"}],
         "data": trend.to_dict("records"), "value_format": "pct"},
        {"id": "recall_by_type", "type": "hbar", "title": "On-time completion by follow-up type", "x": "followup_type",
         "series": [{"key": "on_time_pct", "label": "% on time"}], "data": by_type.to_dict("records"),
         "value_format": "pct"},
    ]
    return _result("followup_completion", "Follow-up (recall) completion", sql, narrative, charts, _table(by_type),
                   [f"Follow-ups due in the last {grace_days} days are excluded (grace period still open)."],
                   definition=f"Recall completion = follow-ups completed ≤ {grace_days} days after the documented due "
                              f"date ÷ follow-ups due in the period (excluding cancelled).")


def deliveries(p: Params) -> dict:
    start = p.start or p.ref.replace(day=1)
    end = p.end or p.ref
    f, fp = _fac(p)
    sql = f"""SELECT COALESCE(delivery_mode, 'Not documented') AS delivery_mode, COUNT(*) AS deliveries
              FROM v_pregnancies WHERE delivery_date BETWEEN :start AND :end{f} GROUP BY delivery_mode"""
    df = _q(sql, {"start": start.isoformat(), "end": end.isoformat(), **fp})
    total = int(df["deliveries"].sum())
    label = p.period_label or f"{start:%d %b} - {end:%d %b %Y}"
    narrative = f"{total} deliveries were documented in {label}" + (
        ": " + ", ".join(f"{r.deliveries} {r.delivery_mode.lower()}" for r in df.itertuples()) + "." if total else ".")
    chart = {"id": "deliveries", "type": "hbar", "title": f"Deliveries by documented mode - {label}",
             "x": "delivery_mode", "series": [{"key": "deliveries", "label": "Deliveries"}],
             "data": df.to_dict("records"), "value_format": "int"}
    return _result("deliveries", "Deliveries", sql, narrative, [chart], _table(df),
                   stats=[{"label": "Deliveries", "value": total}])


def pnc_coverage(p: Params) -> dict:
    cut = p.ref - timedelta(days=42)
    start = p.start or (p.ref - timedelta(days=365))
    f, fp = _fac(p, "p.")
    sql = f"""SELECT p.pregnancy_id, v.visit_type FROM v_pregnancies p
              LEFT JOIN v_visits v ON v.patient_key = p.patient_key AND v.visit_category = 'PNC'
                   AND v.status = 'completed' AND v.visit_date >= p.delivery_date
              WHERE p.delivery_date IS NOT NULL AND p.delivery_date BETWEEN :start AND :cut{f}"""
    df = _q(sql, {"start": start.isoformat(), "cut": cut.isoformat(), **fp})
    n = df["pregnancy_id"].nunique()
    data = [{"contact": lab, "coverage_pct": _pct(df[df["visit_type"] == lab]["pregnancy_id"].nunique(), n)}
            for lab in ("PNC-D3", "PNC-D7", "PNC-D42")]
    narrative = f"Among {n} deliveries with a completed 6-week postnatal window: " + \
                ", ".join(f"{d['contact']} {d['coverage_pct']}%" for d in data) + "."
    chart = {"id": "pnc", "type": "bar", "title": "Postnatal contact coverage", "x": "contact",
             "series": [{"key": "coverage_pct", "label": "% of deliveries"}], "data": data, "value_format": "pct"}
    return _result("pnc_coverage", "PNC coverage", sql, narrative, [chart], _table(pd.DataFrame(data)))


def pregnancy_status(p: Params) -> dict:
    f, fp = _fac(p)
    sql = f"SELECT status, COUNT(*) AS pregnancies FROM v_pregnancies WHERE 1=1{f} GROUP BY status"
    df = _q(sql, fp)
    labels = {"antenatal": "Currently antenatal", "delivered": "Delivered (< 6 weeks)",
              "postnatal_closed": "Postnatal period completed", "no_recent_contact": "No recent contact"}
    stats = [{"label": labels.get(r.status, r.status), "value": int(r.pregnancies)} for r in df.itertuples()]
    narrative = "Registered pregnancies by current status: " + ", ".join(f"{s['label']} {s['value']}" for s in stats) + "."
    return _result("pregnancy_status", "Registered pregnancies", sql, narrative, stats=stats, table=_table(df),
                   caveats=["'No recent contact' = EDD passed without a documented delivery, or no visit for 10+ weeks "
                            "- an operational flag for tracing, not a clinical status."])


def followup_backlog(p: Params) -> dict:
    f, fp = _fac(p)
    sql = f"""SELECT facility_name, followup_type, status, COUNT(*) AS n FROM v_followups
              WHERE status IN ('due', 'overdue', 'missed'){f} GROUP BY facility_name, followup_type, status"""
    df = _q(sql, fp)
    piv = df.pivot_table(index="followup_type", columns="status", values="n", aggfunc="sum", fill_value=0).reset_index()
    for c in ("due", "overdue", "missed"):
        if c not in piv:
            piv[c] = 0
    narrative = f"Open documented follow-ups: {int(piv['due'].sum())} due within 7 days, {int(piv['overdue'].sum())} " \
                f"overdue (≤ 28 days) and {int(piv['missed'].sum())} missed (> 28 days)."
    chart = {"id": "backlog", "type": "stacked_hbar", "title": "Open follow-ups by type", "x": "followup_type",
             "series": [{"key": "due", "label": "Due ≤ 7 days"}, {"key": "overdue", "label": "Overdue ≤ 28 days"},
                        {"key": "missed", "label": "Missed > 28 days"}],
             "data": piv[["followup_type", "due", "overdue", "missed"]].to_dict("records"), "value_format": "int"}
    return _result("followup_backlog", "Follow-up backlog", sql, narrative, [chart], _table(df))


def facility_comparison(p: Params) -> dict:
    start = p.start or (p.ref - timedelta(days=90))
    sql = """SELECT facility_name, facility_source, status, visit_category, COUNT(*) AS n FROM v_visits
             WHERE visit_date BETWEEN :start AND :end GROUP BY facility_name, facility_source, status, visit_category"""
    df = _q(sql, {"start": start.isoformat(), "end": (p.end or p.ref).isoformat()})
    rows = []
    for fac, g in df.groupby("facility_name"):
        comp = int(g[g["status"] == "completed"]["n"].sum())
        anc = g[g["visit_category"] == "ANC"]
        ns = int(anc[anc["status"] == "no_show"]["n"].sum())
        booked = int(anc["n"].sum())
        rows.append({"facility": fac, "completed_visits": comp,
                     "anc_no_show_pct": _pct(ns, booked) if g["facility_source"].iloc[0] == "ehr_export" else None,
                     "source": g["facility_source"].iloc[0]})
    out = pd.DataFrame(rows)
    narrative = "Completed visits since " + f"{start:%d %b %Y}: " + \
                ", ".join(f"{r['facility']} {r['completed_visits']}" for r in rows) + "."
    chart = {"id": "facilities", "type": "hbar", "title": "Completed visits by facility", "x": "facility",
             "series": [{"key": "completed_visits", "label": "Completed visits"}], "data": rows, "value_format": "int"}
    return _result("facility_comparison", "Facility comparison", sql, narrative, [chart], _table(out),
                   ["No-show rate is not available for register-only facilities."])


# =============================================================================== catalogue & matching
CATALOGUE = {
    "visit_count": (visit_count, r"how many .*visits?|number of .*visits?|visits? (this|last) (month|week|year)|count of visits"),
    "visit_volume": (visit_volume, r"visit volume|visits? (by|per) month|monthly visits?|visit trend|volume"),
    "anc_dropoff": (anc_dropoff, r"drop[- ]?off|dropout|drop out|retention|continuation|anc4|anc coverage|funnel"),
    "no_show_trend": (no_show_trend, r"no[- ]?shows?|did not attend|\bdna\b|missed appointments? rate|attendance"),
    "investigation_utilization": (investigation_utilization, r"investigation|lab(oratory)? (tests?|utili)|tests? ordered|"
                                  r"turnaround|utili[sz]ation|pending results"),
    "visit_frequency": (visit_frequency, r"frequency|visits? per (pregnancy|patient|woman)|average (number of )?(anc )?visits|"
                        r"distribution"),
    "registration_timeliness": (registration_timeliness, r"first trimester|early registration|registration (timeliness|trend)"),
    "immunization_coverage": (immunization_coverage, r"immuni[sz]ation coverage|vaccination coverage|immuni[sz]ation rate|"
                              r"coverage of (vaccin|immuni)"),
    "followup_completion": (followup_completion, r"follow[- ]?ups? (completion|completed)|recall|completed on time|"
                            r"on[- ]time"),
    "deliveries": (deliveries, r"deliver(y|ies)|births?|lscs|caesarean|cesarean|c-sections?"),
    "pnc_coverage": (pnc_coverage, r"pnc coverage|postnatal coverage|postnatal (contacts?|visits?) (rate|coverage)"),
    "pregnancy_status": (pregnancy_status, r"how many pregnan|active pregnan|registered pregnan|currently (pregnant|antenatal)"),
    "facility_comparison": (facility_comparison, r"compare (the )?facilit|facility comparison|facility[- ]wise (visits|comparison)|"
                            r"visits across facilities|compare .*across facilities"),
    "followup_backlog": (followup_backlog, r"backlog|open follow[- ]?ups|how many follow[- ]?ups|follow[- ]?ups? (by|per) type"),
}
# More specific metrics win ties.
PRIORITY = ["followup_completion", "anc_dropoff", "no_show_trend", "immunization_coverage", "pnc_coverage",
            "registration_timeliness", "visit_frequency", "investigation_utilization", "deliveries",
            "pregnancy_status", "facility_comparison", "followup_backlog", "visit_count", "visit_volume"]


def match(question: str) -> list[str]:
    q = question.lower()
    hits = [m for m in PRIORITY if re.search(CATALOGUE[m][1], q)]
    if "no_show_trend" in hits and "facility_comparison" in hits:
        hits.remove("no_show_trend")       # "compare no-show rates across facilities"
    return hits


def run(metric_id: str, params: Params) -> dict:
    return CATALOGUE[metric_id][0](params)


def available_metrics() -> list[dict]:
    return [{"id": m, "description": (CATALOGUE[m][0].__doc__ or m.replace('_', ' ')).strip().split("\n")[0]}
            for m in PRIORITY]
