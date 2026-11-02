"""Query orchestrator - the ClinieSync request pipeline (architecture slide, boxes 4-7).

  User query (text/voice)
    -> INPUT GUARD (lexicon, semantic screen, NeMo Guardrails)        [guardrails/]
    -> slot extraction + patient resolution
    -> ACCESS GUARD (role x intent, minimum-necessary scopes)
    -> QUERY ROUTER: SQL analytics | RAG retrieval | hybrid
    -> OUTPUT GUARD (clinical language, grounding, citations, PII, NeMo)
    -> stored as `pending_review` for human verification + audit log
"""
from __future__ import annotations

import re
import time
import uuid
from dataclasses import dataclass
from datetime import date, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ai.llm.client import LLMUnavailable, get_llm
from ai.rag.retriever import Evidence, fmt_d, load_evidence, retrieve_notes
from ai.rag.summarizer import deterministic_summary, llm_answer
from ai.router import parameters as PARAM
from ai.router.slots import Slots, extract
from ai.sql import semantic_layer as SL
from common.settings import get_settings
from database import models as M
from guardrails import access_guard, output_guard
from guardrails.input_guard import InputGuard
from guardrails.nemo_adapter import get_nemo
from guardrails.policy import DISCLAIMER, INTENT_MATRIX, REFUSALS, SUGGESTIONS

INTENT_LABEL = {r["intent"]: r["label"] for r in INTENT_MATRIX}
ROUTE = {"patient_retrieval": "RAG + SQL", "patient_summary": "RAG", "population_analytics": "SQL",
         "care_coordination": "SQL + RAG"}


@dataclass
class UserCtx:
    username: str
    role: str
    display_name: str = ""
    facility_id: str | None = None


# =============================================================================== entry point
def handle_query(s: Session, user: UserCtx, query: str, patient_id: str | None = None,
                 input_mode: str = "text") -> dict:
    t0 = time.time()
    settings = get_settings()
    ref = settings.reference_date
    llm = get_llm()
    llm_ok = llm.available()
    nemo = get_nemo()
    nemo.load(llm_ok)

    has_ctx = bool(patient_id) or bool(re.search(r"\bCS-\d{6}\b", query, re.I))
    decision = InputGuard(nemo).check(query, has_patient_context=has_ctx)
    trace = {"input": decision.layers, "access": None, "output": []}
    base = {"query": decision.redacted_query, "input_mode": input_mode, "llm_available": llm_ok,
            "llm_model": llm.model if llm_ok else None, "disclaimer": DISCLAIMER}

    if not decision.allowed:
        payload = {**base, "status": "blocked", "intent": decision.category,
                   "intent_label": INTENT_LABEL.get(decision.category, decision.category), "route": "blocked",
                   "answer": REFUSALS[decision.category],
                   "refusal": {"category": decision.category, "message": REFUSALS[decision.category],
                               "alternatives": SUGGESTIONS.get(user.role, [])},
                   "guard_trace": trace}
        return _persist(s, user, query, payload, None, t0, "blocked", decision.category)

    intent = decision.intent
    patients = [(p.patient_id, p.full_name) for p in s.execute(select(M.Patient.patient_id, M.Patient.full_name))]
    facilities = [(f.facility_id, f.name) for f in s.scalars(select(M.Facility))]
    slots = extract(query, ref, patients, facilities)
    pid = slots.patient_ids[0] if slots.patient_ids else patient_id
    if not pid and len(slots.patient_name_candidates) == 1:
        pid = slots.patient_name_candidates[0][0]
    if intent in ("patient_retrieval", "patient_summary") and not pid and user.role == "admin":
        intent = "population_analytics"
    patient_level = intent in ("patient_retrieval", "patient_summary")
    acc = access_guard.check(user.role, intent, patient_level)
    trace["access"] = {"verdict": "pass" if acc.allowed else "block", "detail": acc.detail}
    if not acc.allowed:
        payload = {**base, "status": "blocked", "intent": "access", "intent_label": "Access control",
                   "route": "blocked", "answer": REFUSALS["access"],
                   "refusal": {"category": "access", "message": REFUSALS["access"],
                               "alternatives": SUGGESTIONS.get(user.role, [])}, "guard_trace": trace}
        return _persist(s, user, query, payload, None, t0, "blocked", "access")

    if patient_level and not pid:
        cands = slots.patient_name_candidates[:6]
        payload = {**base, "status": "needs_clarification", "intent": intent, "intent_label": INTENT_LABEL[intent],
                   "route": ROUTE[intent],
                   "answer": "Which patient do you mean? Open the patient in **Patient Journey**, or include the "
                             "ClinieSync ID (e.g. CS-000123) in your question.",
                   "candidates": [{"patient_id": a, "name": b} for a, b in cands], "guard_trace": trace}
        return _persist(s, user, query, payload, None, t0, "info", intent)

    if patient_level and not s.get(M.Patient, pid):
        payload = {**base, "status": "needs_clarification", "intent": intent, "intent_label": INTENT_LABEL[intent],
                   "route": ROUTE[intent], "answer": f"No patient with ID {pid} was found.", "guard_trace": trace}
        return _persist(s, user, query, payload, None, t0, "info", intent)

    if intent == "population_analytics":
        result = _analytics(query, slots, user, ref, llm_ok)
    elif intent == "care_coordination":
        result = _coordination(s, query, slots, user, ref, pid if has_ctx else None)
    else:
        ev = load_evidence(s, pid, acc.scopes, query)
        if intent == "patient_summary":
            result = _summary(ev, query, acc.scopes, ref, llm_ok)
        else:
            result = _retrieval(s, ev, query, slots, acc.scopes, ref, llm_ok)
        result["patient"] = {"patient_id": ev.patient.patient_id, "name": ev.patient.full_name,
                             "preferred_language": ev.patient.preferred_language}

    # ---- output guard (with deterministic fallback for LLM text) -------------------------------
    ev_obj: Evidence | None = result.pop("_evidence", None)
    fallback = result.pop("_fallback", None)
    od = output_guard.check(result["answer"], evidence_text=ev_obj.blob() if ev_obj else "",
                            evidence_ids=ev_obj.ids() if ev_obj else set(), role=user.role,
                            generated_by=result.get("generated_by", "template"), user_text=query, nemo=nemo,
                            evidence_items={i.id: f"{i.title}: {i.text}" for i in ev_obj.items} if ev_obj else None)
    trace["output"] = od.checks
    if not od.passed:
        if fallback:
            result["answer"], result["generated_by"] = fallback, "template"
            result.setdefault("notes", []).append("The model's draft failed an output check and was replaced by the "
                                                  "record-built summary.")
            od2 = output_guard.check(fallback, evidence_text="", evidence_ids=set(), role=user.role,
                                     generated_by="template")
            trace["output"] += [{**c, "check": c["check"] + " (fallback)"} for c in od2.checks]
            result["answer"] = od2.text
        else:
            result["answer"] = "The generated answer was withheld by the output safety policy."
    else:
        result["answer"] = od.text

    payload = {**base, "status": "pending_review", "intent": intent, "intent_label": INTENT_LABEL[intent],
               "route": result.pop("route", ROUTE[intent]), **result, "guard_trace": trace,
               "slots": slots.as_dict()}
    return _persist(s, user, query, payload, payload.get("patient", {}).get("patient_id"), t0, "pending_review", intent)


# =============================================================================== handlers
def _summary(ev: Evidence, query: str, scopes: set[str], ref: date, llm_ok: bool) -> dict:
    det = deterministic_summary(ev, scopes, ref)
    out = {"route": "RAG", "answer": det, "generated_by": "template", "_evidence": ev, "_fallback": det,
           "citations": [i.as_dict() for i in ev.items]}
    if llm_ok:
        try:
            out["answer"] = llm_answer(ev, query, "summary")
            out["generated_by"] = "llm"
        except LLMUnavailable:
            pass
    actions = [{"type": "share_report", "label": "Share report"}] if "share_reports" in scopes else []
    return {**out, "actions": actions}


def _retrieval(s: Session, ev: Evidence, query: str, slots: Slots, scopes: set[str], ref: date, llm_ok: bool) -> dict:
    q = query.lower()
    cites = lambda refs: [i.as_dict() for i in ev.items if (i.ref_type, i.ref_id) in refs]  # noqa: E731
    name = f"{ev.patient.full_name} ({ev.patient.patient_id})"

    # --- named parameters / tests (haemoglobin, BP, weight, OGTT, TSH, ultrasound ...): visit readings + lab reports
    params = PARAM.detect(q)
    if params or (PARAM.GENERIC_VALUES.search(q) and not re.search(r"\b(reports?|investigations?|tests?|labs?)\b", q)):
        return _parameter_values(ev, q, params or [PARAM.BY_KEY[k] for k in PARAM.DEFAULT_KEYS], slots, scopes, name, cites)

    # --- investigations / reports
    if re.search(r"\b(investigations?|labs?|reports?|results?|tests?|ogtt|usg|scans?|ultrasound|cbc|hiv|vdrl|hbsag|tsh)\b", q):
        inv = ev.investigations
        if re.search(r"pending|awaiting|not (yet )?(resulted|available)|without result", q):
            inv = [i for i in inv if i.status == "pending"]
        if slots.n_last:
            inv = inv[-slots.n_last * 6:]
        rows = [{"test": i.test_name, "ordered_on": i.ordered_on.isoformat(), "status": i.status,
                 "resulted_on": i.resulted_on.isoformat() if i.resulted_on else None,
                 **({"documented_result": i.result_summary} if "clinical_values" in scopes else {})} for i in inv]
        cols = [{"key": "test", "label": "Investigation"}, {"key": "ordered_on", "label": "Ordered"},
                {"key": "status", "label": "Status"}, {"key": "resulted_on", "label": "Resulted"}]
        if "clinical_values" in scopes:
            cols.append({"key": "documented_result", "label": "Documented result"})
        pend = sum(i.status == "pending" for i in inv)
        txt = f"{len(inv)} investigation(s) listed for {name}; {pend} without a documented result."
        return {"route": "SQL", "answer": txt, "generated_by": "template", "table": {"columns": cols, "rows": rows},
                "citations": cites({("investigation", i.investigation_id) for i in inv})}

    # --- follow-ups for this patient
    if re.search(r"follow[- ]?ups?|appointments?|due|overdue|next visit", q):
        fus = ev.followups
        if re.search(r"pending|open|due|overdue", q):
            fus = [f for f in fus if f.status in ("due", "overdue", "missed", "upcoming")]
        rows = [{"type": f.followup_type, "due_on": f.due_on.isoformat(), "status": f.status,
                 "documented_instruction": f.description, "workflow_state": f.workflow_state} for f in fus]
        txt = f"{len(fus)} documented follow-up(s) for {name}" + (
            f"; next open item: {fus[0].followup_type} due {fmt_d(fus[0].due_on)} ({fus[0].status})." if fus else ".")
        return {"route": "SQL", "answer": txt, "generated_by": "template",
                "table": {"columns": [{"key": "type", "label": "Follow-up"}, {"key": "due_on", "label": "Due"},
                                      {"key": "status", "label": "Status"},
                                      {"key": "documented_instruction", "label": "Documented instruction"},
                                      {"key": "workflow_state", "label": "Coordination"}], "rows": rows},
                "citations": cites({("followup", f.followup_id) for f in fus})}

    # --- immunizations
    if re.search(r"immuni[sz]|vaccin|baby|child", q):
        rows = [{"session": im.schedule_label, "vaccine": im.vaccine, "due_on": im.due_on.isoformat(),
                 "given_on": im.given_on.isoformat() if im.given_on else None, "status": im.status}
                for im in ev.immunizations]
        txt = f"{len(rows)} vaccine doses tracked for the child of {name}." if rows else \
            f"No child immunization records are linked to {name}."
        return {"route": "SQL", "answer": txt, "generated_by": "template",
                "table": {"columns": [{"key": k, "label": k.replace('_', ' ').capitalize()} for k in
                                      ("session", "vaccine", "due_on", "given_on", "status")], "rows": rows},
                "citations": cites({("child", c.child_id) for c in ev.children})}

    # --- notes / documented narrative (RAG)
    if re.search(r"\b(notes?|documented|medications?|medicines?|advised|plan|delivery|discharge|mention\w*|said|"
                 r"written|complaints?|counsell\w*)\b", q) and "notes" in scopes:
        hits = retrieve_notes(ev.patient.patient_id, query, k=4)
        refs = {("document", h["doc_id"]) for h in hits}
        extract_txt = "\n".join(f"- **{h['title']}** ({h['doc_date']}): " + h["text"].replace("\n", " ")[:260] + "… "
                                + f"[{ev.find('document', h['doc_id'])}]" for h in hits)
        det = f"Most relevant documented notes for {name}:\n{extract_txt}" if hits else "No matching notes found."
        out = {"route": "RAG", "answer": det, "generated_by": "template", "_evidence": ev, "_fallback": det,
               "citations": cites(refs)}
        if llm_ok and hits:
            try:
                out["answer"], out["generated_by"] = llm_answer(ev, query, "qa"), "llm"
            except LLMUnavailable:
                pass
        return out

    # --- visits / history / timeline (default)
    visits = [v for v in ev.visits]
    if slots.n_last:
        visits = [v for v in visits if v.status == "completed"][-slots.n_last:]
    rows = []
    for v in reversed(visits):
        row = {"date": v.visit_date.isoformat(), "visit": v.visit_type, "facility": ev.facility_names.get(v.facility_id),
               "ga_weeks": v.ga_weeks, "status": v.status}
        if "clinical_values" in scopes:
            from ai.rag.retriever import _vitals_text

            row["recorded"] = _vitals_text(ev.observations.get(v.visit_id, []))
        rows.append(row)
    cols = [{"key": "date", "label": "Date"}, {"key": "visit", "label": "Visit"}, {"key": "facility", "label": "Facility"},
            {"key": "ga_weeks", "label": "GA (w)"}, {"key": "status", "label": "Status"}]
    if "clinical_values" in scopes:
        cols.append({"key": "recorded", "label": "Recorded at visit"})
    label = f"last {slots.n_last} completed" if slots.n_last else "all documented"
    txt = f"Showing {label} visits for {name} ({len(rows)} rows, newest first)."
    return {"route": "SQL", "answer": txt, "generated_by": "template", "table": {"columns": cols, "rows": rows},
            "citations": cites({("visit", v.visit_id) for v in visits})}


def _parameter_values(ev: Evidence, q: str, params: list[PARAM.Parameter], slots: Slots, scopes: set[str],
                      name: str, cites) -> dict:
    """Documented values of the requested parameters: readings recorded at visits and the matching lab / imaging
    reports, newest first, verbatim (no reference ranges, no interpretation)."""
    labels = ", ".join(p.label for p in params)
    inv_codes = {c for p in params for c in p.investigation_codes}
    invs = [i for i in ev.investigations if i.test_code in inv_codes]
    if re.search(r"\b(pending|awaiting|not (yet )?(resulted|available)|without (a )?result)\b", q):
        invs = [i for i in invs if i.status == "pending"]
    if "clinical_values" not in scopes:
        msg = "Recorded clinical values and documented results are visible to doctors only (minimum-necessary access)."
        if not invs:
            none = f" No {labels} test is documented for this patient." if inv_codes else ""
            return {"route": "SQL", "answer": msg + none + " You can view visit dates and follow-ups for this patient.",
                    "generated_by": "template"}
        rows = [{"test": i.test_name, "ordered_on": i.ordered_on.isoformat(), "status": i.status,
                 "resulted_on": i.resulted_on.isoformat() if i.resulted_on else None} for i in reversed(invs)]
        return {"route": "SQL", "answer": f"{msg} Order and result status of {labels} for {name}: {len(invs)} test(s), "
                f"{sum(i.status == 'pending' for i in invs)} without a documented result.", "generated_by": "template",
                "table": {"columns": [{"key": "test", "label": "Investigation"}, {"key": "ordered_on", "label": "Ordered"},
                                      {"key": "status", "label": "Status"}, {"key": "resulted_on", "label": "Resulted"}],
                          "rows": rows}, "citations": cites({("investigation", i.investigation_id) for i in invs})}

    if slots.start and slots.end:                       # "BP readings over the last 3 months", "Hb in August"
        in_window = lambda d: d is not None and slots.start <= d <= slots.end  # noqa: E731
        invs = [i for i in invs if in_window(i.resulted_on or i.ordered_on)]
    else:
        in_window = lambda d: True  # noqa: E731
    latest_only = re.search(r"\b(latest|most recent|current)\b|\blast\b(?!\s+(\d+\s+)?(weeks?|months?|years?|trimesters?)\b)", q)
    keep = slots.n_last or (1 if latest_only else None)
    rows, series, refs, lines = [], {}, set(), []
    for p in params:
        readings = []                                   # (date, value text, numeric points, visit) per visit
        for v in ev.visits:
            obs = {o.code: o for o in ev.observations.get(v.visit_id, []) if o.code in p.observation_codes}
            if not obs:
                continue
            if p.key == "blood_pressure" and {"bp_systolic", "bp_diastolic"} <= obs.keys():
                val = f"{obs['bp_systolic'].value_num:g}/{obs['bp_diastolic'].value_num:g} mmHg"
            else:
                val = "; ".join(f"{o.value_num:g} {o.unit or ''}".strip() if o.value_num is not None else (o.value_text or "")
                                for o in obs.values())
            if in_window(v.visit_date):
                readings.append((v.visit_date, val, obs, v))
        if p.key == "infant_weight":                    # birth weight is documented on the child record
            for c in ev.children:
                if c.birth_weight_g and in_window(c.dob):
                    readings.append((c.dob, f"{c.birth_weight_g / 1000:g} kg (birth weight)", {}, None))
                    refs.add(("child", c.child_id))
            readings.sort(key=lambda r: r[0])
        p_invs = [i for i in invs if i.test_code in p.investigation_codes]
        shown_r = readings[-keep:] if keep else readings
        shown_i = p_invs[-keep:] if keep else p_invs
        for d, val, obs, v in shown_r:
            rows.append({"date": d.isoformat(), "parameter": p.label, "value": val,
                         "source": f"{v.visit_type} visit" if v else "Child record"})
            for code, o in obs.items():
                if o.value_num is not None:
                    series.setdefault(code, []).append({"date": d.isoformat(), "value": o.value_num,
                                                        "visit_type": v.visit_type, "ga_weeks": v.ga_weeks})
            if v:
                refs.add(("visit", v.visit_id))
        for i in shown_i:
            rows.append({"date": (i.resulted_on or i.ordered_on).isoformat(), "parameter": p.label,
                         "value": i.result_summary or "no result documented yet",
                         "source": f"Lab report · {i.test_name} ({'resulted' if i.status == 'resulted' else 'ordered, ' + i.status})"})
            refs.add(("investigation", i.investigation_id))

        parts = []
        if p.observation_codes:
            if readings:
                d, val, _, v = readings[-1]
                cite = ev.find("visit", v.visit_id) if v else ev.find("child", ev.children[0].child_id)
                parts.append(f"{len(readings)} recorded reading(s); most recent {val} on {fmt_d(d)}"
                             + (f" ({v.visit_type})" if v else "") + (f" [{cite}]" if cite else ""))
            else:
                parts.append("no readings recorded" + (f" in {slots.period_label}" if slots.period_label else ""))
        if p.investigation_codes:
            if p_invs:
                done = [i for i in p_invs if i.status == "resulted"]
                last = done[-1] if done else None
                txt = f"{len(p_invs)} lab/imaging report(s), {len(p_invs) - len(done)} without a documented result"
                if last:
                    txt += f"; latest resulted {fmt_d(last.resulted_on)} [{ev.find('investigation', last.investigation_id)}]"
                parts.append(txt)
            elif not p.observation_codes:
                parts.append(f"no {p.label} test documented for this patient"
                             + (f" in {slots.period_label}" if slots.period_label else ""))
        lines.append(f"- **{p.label}**: " + "; ".join(parts) + ".")

    scope_txt = (f"the last {keep} value(s) per parameter" if keep else "all documented values") + \
        (f", {slots.period_label}" if slots.period_label else "")
    txt = (f"Documented {labels} for {name}, exactly as recorded (no interpretation; {scope_txt} in the table):\n"
           + "\n".join(lines))
    return {"route": "SQL", "answer": txt, "generated_by": "template",
            "measurements": series or None,
            "table": {"columns": [{"key": "date", "label": "Date"}, {"key": "parameter", "label": "Parameter"},
                                  {"key": "value", "label": "Value / documented result"},
                                  {"key": "source", "label": "Source"}],
                      "rows": sorted(rows, key=lambda r: r["date"], reverse=True)},
            "citations": cites(refs)}


def _coordination(s: Session, query: str, slots: Slots, user: UserCtx, ref: date, ctx_pid: str | None) -> dict:
    if user.role == "admin":
        r = SL.run("followup_backlog", SL.Params(ref=ref, facility_id=slots.facility_id))
        return {"route": "SQL", "answer": r["narrative"], "generated_by": "template", "charts": r["charts"],
                "table": r["table"], "sql": r["sql"], "caveats": ["Administrators see aggregate counts only."]}
    stmt = select(M.FollowUp, M.Patient).join(M.Patient, M.Patient.patient_id == M.FollowUp.patient_id)
    statuses = slots.status or ["due", "overdue"]
    if "missed" in query.lower() and "missed" not in statuses:
        statuses.append("missed")
    stmt = stmt.where(M.FollowUp.status.in_(statuses))
    if slots.followup_type:
        stmt = stmt.where(M.FollowUp.followup_type == slots.followup_type)
    if slots.facility_id:
        stmt = stmt.where(M.FollowUp.facility_id == slots.facility_id)
    if user.facility_id:
        stmt = stmt.where(M.FollowUp.facility_id == user.facility_id)
    if slots.start and slots.end and ("due" in statuses or "upcoming" in statuses):
        stmt = stmt.where(M.FollowUp.due_on.between(slots.start, slots.end))
    if ctx_pid:
        stmt = stmt.where(M.FollowUp.patient_id == ctx_pid)
    rows_db = s.execute(stmt.order_by(M.FollowUp.due_on)).all()
    fac = {f.facility_id: f.name for f in s.scalars(select(M.Facility))}
    rows = []
    for f, p in rows_db:
        days = (ref - f.due_on).days
        rows.append({"followup_id": f.followup_id, "patient_id": p.patient_id, "patient": p.full_name,
                     "type": f.followup_type, "due_on": f.due_on.isoformat(),
                     "days_past_due": days if days > 0 else 0, "status": f.status, "facility": fac.get(f.facility_id),
                     "language": p.preferred_language, "phone": p.phone, "workflow_state": f.workflow_state,
                     "attempts": f.contact_attempts, "documented_instruction": f.description})
    rows.sort(key=lambda r: -r["days_past_due"])
    by_type: dict[str, int] = {}
    for r in rows:
        by_type[r["type"]] = by_type.get(r["type"], 0) + 1
    txt = (f"{len(rows)} documented follow-up(s) with status {', '.join(statuses)}"
           + (f" ({slots.period_label})" if slots.period_label else "") + ": "
           + ", ".join(f"{v} {k}" for k, v in by_type.items()) + ". Sorted by days past due (operational order, "
           "not clinical priority).") if rows else "No documented follow-ups match these filters."
    actions = []
    if rows and re.search(r"remind|prompt|draft|send|message|sms|whatsapp|automat", query.lower()):
        actions.append({"type": "draft_reminders", "label": f"Draft reminders for {min(len(rows), 50)} patients "
                        "(you approve before anything is sent)", "followup_ids": [r["followup_id"] for r in rows[:50]]})
    elif rows:
        actions.append({"type": "open_followups", "label": "Open in Follow-up queue"})
    cols = [{"key": "patient", "label": "Patient"}, {"key": "patient_id", "label": "ID"}, {"key": "type", "label": "Follow-up"},
            {"key": "due_on", "label": "Due"}, {"key": "days_past_due", "label": "Days past due"},
            {"key": "status", "label": "Status"}, {"key": "facility", "label": "Facility"},
            {"key": "language", "label": "Lang"}, {"key": "workflow_state", "label": "Coordination"}]
    return {"route": "SQL + RAG", "answer": txt, "generated_by": "template", "table": {"columns": cols, "rows": rows[:200]},
            "actions": actions, "caveats": ["Every follow-up shown was documented by clinic staff (appointment, register "
                                            "or note); ClinieSync does not decide who needs follow-up."]}


def _analytics(query: str, slots: Slots, user: UserCtx, ref: date, llm_ok: bool) -> dict:
    metrics = SL.match(query)
    params = SL.Params(ref=ref, start=slots.start, end=slots.end, period_label=slots.period_label,
                       facility_id=slots.facility_id)
    # "which/per/by facility" breakdowns: governed metrics are facility-agnostic, so try validated text-to-SQL first
    by_facility = bool(re.search(r"\b(which|per|by|each) facilit", query, re.I)) and \
        (not metrics or metrics[0] != "facility_comparison")
    if llm_ok and (not metrics or by_facility):
        from ai.sql.text_to_sql import generate_and_run

        try:
            r = generate_and_run(query, user.role, ref)
        except LLMUnavailable:
            r = {"ok": False, "reason": "model unavailable"}
        if r.get("ok"):
            return {"route": "SQL (LLM-generated, validated)", "answer": f"{r['title']}: {r['rows']} row(s).",
                    "generated_by": "template", "charts": [r["chart"]] if r["chart"] else [], "table": r["table"],
                    "sql": r["sql"], "caveats": ["SQL generated by the open-source LLM, validated (read-only, "
                                                 "de-identified views, aggregate-only for administrators)."]}
    if metrics:
        main = SL.run(metrics[0], params)
        extra = [SL.run(m, params) for m in metrics[1:2]]
        charts = main["charts"] + [c for e in extra for c in e["charts"]]
        answer = main["narrative"] + "".join(" " + e["narrative"] for e in extra)
        return {"route": "SQL", "answer": answer, "generated_by": "template", "charts": charts, "table": main["table"],
                "stats": main["stats"], "sql": main["sql"], "caveats": main["caveats"],
                "definition": main["definition"], "metric": main["metric"]}
    catalogue = ", ".join(m.replace("_", " ") for m in SL.PRIORITY)
    return {"route": "SQL", "answer": "I couldn't map this to a governed metric" +
            ("" if llm_ok else " (and the LLM text-to-SQL fallback is offline)") +
            f". Available analytics: {catalogue}.", "generated_by": "template"}


# =============================================================================== persistence + audit
def _persist(s: Session, user: UserCtx, query: str, payload: dict, patient_id: str | None, t0: float,
             status: str, intent: str) -> dict:
    from guardrails.pii import redact

    rid = uuid.uuid4().hex[:16]
    latency = int((time.time() - t0) * 1000)
    payload = {**payload, "response_id": rid, "latency_ms": latency, "status": payload.get("status", status)}
    s.add(M.AIResponse(response_id=rid, created_at=datetime.now(), username=user.username, role=user.role,
                       query_text=redact(query), input_mode=payload.get("input_mode", "text"), intent=intent,
                       route=str(payload.get("route", "-")), patient_id=patient_id,
                       answer_text=payload.get("answer", ""), payload=_jsonable(payload),
                       llm_used=payload.get("generated_by") == "llm", latency_ms=latency, status=status))
    s.add(M.AuditLog(at=datetime.now(), username=user.username, role=user.role, action="query",
                     target=patient_id or intent, decision="blocked" if status == "blocked" else "allowed",
                     detail={"response_id": rid, "intent": intent, "query": redact(query),
                             "input_mode": payload.get("input_mode"), "latency_ms": latency}))
    s.flush()
    return payload


def _jsonable(o):
    if isinstance(o, dict):
        return {k: _jsonable(v) for k, v in o.items()}
    if isinstance(o, (list, tuple, set)):
        return [_jsonable(v) for v in o]
    if isinstance(o, (date, datetime)):
        return o.isoformat()
    if hasattr(o, "item"):
        o = o.item()
    if isinstance(o, float) and o != o:   # NaN -> null (browsers reject NaN in JSON)
        return None
    return o


def query_stats(s: Session) -> dict:
    rows = s.execute(select(M.AIResponse.status, func.count()).group_by(M.AIResponse.status)).all()
    return {k: v for k, v in rows}


__all__ = ["handle_query", "UserCtx", "query_stats"]
