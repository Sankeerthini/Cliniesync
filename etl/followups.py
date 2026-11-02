"""Documented follow-ups: build the follow-up registry and derive each item's status.

Sources of follow-ups (all DOCUMENTED by clinic staff - ClinieSync never decides
that a patient *needs* a follow-up):
  1. EHR appointments (booked next visits, report reviews, PNC, immunization)
  2. Register "Next Due Date" column
  3. Instructions written in clinical notes ("Review after 2 weeks with reports")
     - extracted with transparent regex rules; the verbatim sentence and the
       source document ID are stored so the UI can cite them.

Status is computed from what happened afterwards (a matching completed visit).
"""
from __future__ import annotations

import re
from collections import defaultdict
from datetime import date, timedelta

import pandas as pd

from common.settings import get_settings
from etl import vocab as V
from etl.clean import blank, parse_date

NOTE_RULES = [
    # (regex, followup type, how to compute the due date)
    (re.compile(r"Next ANC visit on (\d{2}/\d{2}/\d{4})(?: \(([^)]+)\))?\."), "ANC visit", "date1"),
    (re.compile(r"Follow-up: (\S+) due (\d{2}-\w{3}-\d{4})\."), "ANC visit", "date2"),
    (re.compile(r"Review after (\d+) weeks? for ([^.\n]+)\."), "ANC visit", "weeks"),
    (re.compile(r"Review after (\d+) weeks? with investigation reports\."), "Investigation review", "weeks"),
    (re.compile(r"Next due: ([^\n]+?) on (\d{2}/\d{2}/\d{4})\."), "Immunization", "date2"),
]


def extract_from_notes(docs: pd.DataFrame) -> list[dict]:
    out = []
    for d in docs.to_dict("records"):
        if d["doc_type"] not in ("clinical_note", "immunization_record", "discharge_summary"):
            continue
        for rx, ftype, mode in NOTE_RULES:
            for m in rx.finditer(d["text"]):
                if mode == "date1":
                    due = parse_date(m.group(1))
                elif mode == "date2":
                    due = parse_date(m.group(2))
                else:
                    due = d["doc_date"] + timedelta(weeks=int(m.group(1)))
                if not due:
                    continue
                label = None
                if ftype == "Immunization":
                    label = V.SESSION_BY_LABEL.get(m.group(1).strip())
                out.append({"patient_id": d["patient_id"], "child_id": None if blank(d["child_id"]) else d["child_id"],
                            "followup_type": ftype,
                            "expected_visit_type": label, "due_on": due, "description": m.group(0).strip(),
                            "source_doc_id": d["doc_id"],
                            "source_visit_id": None if blank(d["visit_id"]) else d["visit_id"]})
    return out


def build_followups(t, appointments: pd.DataFrame, reference_date: date) -> tuple[pd.DataFrame, dict]:
    """`t` is the Transformer (gives id maps + canonical frames)."""
    s = get_settings()
    visits = t.out["visits"]
    preg = t.out["pregnancies"]
    patients = t.out["patients"].set_index("patient_id")
    preg_by_patient = defaultdict(list)
    for p in preg.to_dict("records"):
        preg_by_patient[p["patient_id"]].append(p)
    visit_date = dict(zip(visits["visit_id"], visits["visit_date"]))
    visit_preg = dict(zip(visits["visit_id"], visits["pregnancy_id"]))

    items: list[dict] = []
    for r in appointments.to_dict("records"):
        pid = t._pid(r["source_system"], r["source_patient_id"])
        due = parse_date(r["due"])
        if not pid or not due:
            t.q.add(r["source_system"], "followups", "unlinked patient or bad due date", r)
            continue
        ftype, label = V.appointment_type(r["purpose_raw"])
        src_vid = t.visit_map.get((r["source_system"], r["source_encounter_id"])) if r["source_encounter_id"] else None
        if r["purpose_raw"].startswith("Next due (register)"):
            delivered = next((p["delivery_date"] for p in preg_by_patient[pid] if p["delivery_date"]), None)
            ftype = "PNC visit" if delivered and due > delivered else "ANC visit"
        items.append({"patient_id": pid,
                      "child_id": t.child_map.get((r["source_system"], r["source_child_id"])) if r["source_child_id"] else None,
                      "facility_id": r["facility_id"], "source_visit_id": src_vid, "source_doc_id": None,
                      "followup_type": ftype, "expected_visit_type": label, "due_on": due,
                      "description": f"{r['purpose_raw']} (booked {'at visit on ' + visit_date[src_vid].strftime('%d %b %Y') if src_vid else 'in register'})",
                      "origin": "register" if r["source_system"].startswith("excel") else "appointment"})

    # the same instruction can be booked twice (e.g. re-booked after a no-show) -> keep one
    seen, unique = set(), []
    for it in items:
        k = (it["patient_id"], it["child_id"], it["followup_type"], it["due_on"])
        if k not in seen:
            seen.add(k)
            unique.append(it)
    items = unique

    # documented instructions in notes -> attach to matching appointment or create new
    extracted = extract_from_notes(t.out["documents"])
    matched = created = 0
    index = defaultdict(list)
    for it in items:
        index[(it["patient_id"], it["followup_type"])].append(it)
    for c in extracted:
        cand = [i for i in index[(c["patient_id"], c["followup_type"])]
                if abs((i["due_on"] - c["due_on"]).days) <= 7 and i["child_id"] == c["child_id"]]
        if cand:
            target = cand[0]
            if not target["source_doc_id"]:
                target["source_doc_id"] = c["source_doc_id"]
                target["description"] = c["description"]
            matched += 1
        else:
            fac = patients.loc[c["patient_id"], "facility_id"]
            if c["source_visit_id"] in visit_date:
                fac = visits.loc[visits["visit_id"] == c["source_visit_id"], "facility_id"].iloc[0]
            new = {**c, "facility_id": fac, "origin": "note_extraction"}
            items.append(new)
            index[(c["patient_id"], c["followup_type"])].append(new)
            created += 1

    # status derivation
    comp = visits[visits["status"] == "completed"]
    by_patient = defaultdict(list)
    for v in comp.to_dict("records"):
        by_patient[v["patient_id"]].append(v)
    rows = []
    for n, it in enumerate(sorted(items, key=lambda x: (x["patient_id"], x["due_on"])), 1):
        due = it["due_on"]
        created_on = visit_date.get(it["source_visit_id"], due - timedelta(days=30))
        want = {"ANC visit": {"ANC"}, "PNC visit": {"PNC"}, "Immunization": {"Child"}}.get(it["followup_type"])
        cands = [v for v in by_patient[it["patient_id"]]
                 if v["visit_date"] > created_on
                 and due - timedelta(days=14) <= v["visit_date"] <= due + timedelta(days=s.followup_match_window_days)
                 and (want is None or v["visit_category"] in want)
                 and (it["followup_type"] != "Immunization" or v["child_id"] == it["child_id"])
                 and (not it["expected_visit_type"] or it["followup_type"] != "Immunization"
                      or v["visit_type"] == it["expected_visit_type"])]
        cands.sort(key=lambda v: v["visit_date"])
        prid = visit_preg.get(it["source_visit_id"])
        if not prid:
            prid = next((p["pregnancy_id"] for p in preg_by_patient[it["patient_id"]]
                         if p["lmp"] <= due <= (p["delivery_date"] or p["edd"]) + timedelta(days=300)), None)
        delivered = next((p["delivery_date"] for p in preg_by_patient[it["patient_id"]]
                          if p["pregnancy_id"] == prid and p["delivery_date"]), None)
        status, completed_vid, completed_on = None, None, None
        if cands:
            status, completed_vid, completed_on = "completed", cands[0]["visit_id"], cands[0]["visit_date"]
        elif it["followup_type"] == "ANC visit" and delivered and delivered <= due:
            status = "cancelled"     # superseded by delivery
        else:
            days = (reference_date - due).days
            if days > s.missed_after_days:
                status = "missed"
            elif days > 0:
                status = "overdue"
            elif -days <= 7:
                status = "due"
            else:
                status = "upcoming"
        rows.append({"followup_id": f"FU-{n:06d}", "patient_id": it["patient_id"], "child_id": it["child_id"],
                     "pregnancy_id": prid, "facility_id": it["facility_id"], "source_visit_id": it["source_visit_id"],
                     "source_doc_id": it["source_doc_id"], "followup_type": it["followup_type"],
                     "expected_visit_type": it["expected_visit_type"], "description": it["description"][:240],
                     "due_on": due, "due_month": due.strftime("%Y-%m"), "status": status,
                     "completed_visit_id": completed_vid, "completed_on": completed_on, "origin": it["origin"],
                     "workflow_state": "none", "contact_attempts": 0})
    df = pd.DataFrame(rows)
    report = {"from_appointments_and_registers": len(items) - created, "extracted_from_notes": len(extracted),
              "note_instructions_matched_to_appointments": matched, "new_followups_from_notes": created,
              "status_counts": df["status"].value_counts().to_dict()}
    return df, report
