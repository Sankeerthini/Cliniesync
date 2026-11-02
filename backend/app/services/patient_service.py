"""Patient registry, longitudinal timeline and measurement series (role-scoped)."""
from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from database import models as M
from etl.vocab import obs_display

LANES = ["Antenatal care", "Investigations", "Delivery & postnatal", "Child immunization", "Follow-ups"]


def list_patients(s: Session, q: str = "", status: str = "", facility_id: str = "", limit: int = 50) -> list[dict]:
    preg = select(M.Pregnancy.patient_id, func.max(M.Pregnancy.lmp).label("lmp")).group_by(M.Pregnancy.patient_id).subquery()
    stmt = select(M.Patient, M.Pregnancy).join(preg, preg.c.patient_id == M.Patient.patient_id) \
        .join(M.Pregnancy, (M.Pregnancy.patient_id == preg.c.patient_id) & (M.Pregnancy.lmp == preg.c.lmp))
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(M.Patient.full_name.ilike(like), M.Patient.patient_id.ilike(like),
                              M.Patient.rch_id.ilike(like), M.Patient.village.ilike(like)))
    if status:
        stmt = stmt.where(M.Pregnancy.status == status)
    if facility_id:
        stmt = stmt.where(M.Patient.facility_id == facility_id)
    rows = s.execute(stmt.order_by(M.Pregnancy.registration_date.desc()).limit(limit)).all()
    fac = {f.facility_id: f.name for f in s.scalars(select(M.Facility))}
    ids = [p.patient_id for p, _ in rows]
    open_fu = dict(s.execute(select(M.FollowUp.patient_id, func.count()).where(
        M.FollowUp.patient_id.in_(ids), M.FollowUp.status.in_(["due", "overdue"])).group_by(M.FollowUp.patient_id)).all())
    return [{"patient_id": p.patient_id, "name": p.full_name, "age": p.age_years, "village": p.village,
             "facility": fac.get(p.facility_id), "language": p.preferred_language, "status": pr.status,
             "edd": pr.edd.isoformat() if pr.edd else None, "anc_visits": pr.anc_visits_completed,
             "open_followups": open_fu.get(p.patient_id, 0)} for p, pr in rows]


def profile(s: Session, pid: str, scopes: set[str], ref: date) -> dict | None:
    p = s.get(M.Patient, pid)
    if not p:
        return None
    fac = {f.facility_id: f.name for f in s.scalars(select(M.Facility))}
    pregs = list(s.scalars(select(M.Pregnancy).where(M.Pregnancy.patient_id == pid).order_by(M.Pregnancy.lmp)))
    kids = list(s.scalars(select(M.Child).where(M.Child.mother_patient_id == pid)))
    sources = [i.source_system for i in s.scalars(select(M.PatientIdentifier).where(M.PatientIdentifier.patient_id == pid))]
    cur = pregs[-1] if pregs else None
    out = {
        "patient_id": p.patient_id, "name": p.full_name, "age": p.age_years, "language": p.preferred_language,
        "village": p.village, "district": p.district, "facility": fac.get(p.facility_id), "rch_id": p.rch_id,
        "sources": sources,
        "pregnancy": None if not cur else {
            "pregnancy_id": cur.pregnancy_id, "gravida": cur.gravida, "parity": cur.parity, "lmp": cur.lmp.isoformat(),
            "edd": cur.edd.isoformat(), "status": cur.status, "registration_date": _iso(cur.registration_date),
            "registration_ga_weeks": cur.registration_ga_weeks, "delivery_date": _iso(cur.delivery_date),
            "delivery_mode": cur.delivery_mode, "anc_visits_completed": cur.anc_visits_completed,
            "ga_today_weeks": round((ref - cur.lmp).days / 7, 1) if cur.status == "antenatal" else None},
        "children": [{"child_id": c.child_id, "name": c.full_name, "sex": c.sex, "dob": _iso(c.dob),
                      "birth_weight_g": c.birth_weight_g} for c in kids],
        "scopes": sorted(scopes),
    }
    if "contact" in scopes:
        out["contact"] = {"phone": p.phone, "email": p.email, "caregiver_name": p.caregiver_name,
                          "caregiver_relation": p.caregiver_relation, "caregiver_phone": p.caregiver_phone,
                          "consent": {"sms": p.consent_sms, "whatsapp": p.consent_whatsapp, "email": p.consent_email}}
    return out


def timeline(s: Session, pid: str, scopes: set[str], ref: date) -> dict:
    fac = {f.facility_id: f.name for f in s.scalars(select(M.Facility))}
    pregs = list(s.scalars(select(M.Pregnancy).where(M.Pregnancy.patient_id == pid).order_by(M.Pregnancy.lmp)))
    events = []
    for v in s.scalars(select(M.Visit).where(M.Visit.patient_id == pid)):
        lane = {"ANC": "Antenatal care", "Delivery": "Delivery & postnatal", "PNC": "Delivery & postnatal",
                "Child": "Child immunization"}[v.visit_category]
        events.append({"lane": lane, "date": v.visit_date.isoformat(), "label": v.visit_type, "status": v.status,
                       "detail": f"{fac.get(v.facility_id)}" + (f" · GA {v.ga_weeks} w" if v.ga_weeks else ""),
                       "ref_type": "visit", "ref_id": v.visit_id})
    for i in s.scalars(select(M.Investigation).where(M.Investigation.patient_id == pid)):
        detail = f"ordered {i.ordered_on:%d %b %Y}" + (f" · resulted {i.resulted_on:%d %b %Y}" if i.resulted_on else
                                                      " · no result documented")
        if "clinical_values" in scopes and i.result_summary:
            detail += f" · {i.result_summary}"
        events.append({"lane": "Investigations", "date": i.ordered_on.isoformat(),
                       "end_date": _iso(i.resulted_on), "label": i.test_name, "status": i.status, "detail": detail,
                       "ref_type": "investigation", "ref_id": i.investigation_id})
    for f in s.scalars(select(M.FollowUp).where(M.FollowUp.patient_id == pid)):
        events.append({"lane": "Follow-ups", "date": f.due_on.isoformat(), "end_date": _iso(f.completed_on),
                       "label": f.followup_type, "status": f.status, "detail": f.description,
                       "ref_type": "followup", "ref_id": f.followup_id})
    kids = [c.child_id for c in s.scalars(select(M.Child).where(M.Child.mother_patient_id == pid))]
    if kids:
        seen = set()
        for im in s.scalars(select(M.Immunization).where(M.Immunization.child_id.in_(kids))):
            key = (im.child_id, im.schedule_label)
            if key in seen or im.given_on:   # given doses already appear as visits
                continue
            seen.add(key)
            events.append({"lane": "Child immunization", "date": im.due_on.isoformat(),
                           "label": f"{im.schedule_label} vaccines", "status": im.status,
                           "detail": "due - not yet documented as given", "ref_type": "immunization",
                           "ref_id": im.imm_id})
    events.sort(key=lambda e: e["date"])
    bands, markers = [], [{"date": ref.isoformat(), "label": "Today"}]
    if pregs:
        p = pregs[-1]
        end = p.delivery_date or p.edd
        bands = [{"label": "1st trimester", "start": p.lmp.isoformat(), "end": (p.lmp + timedelta(weeks=14)).isoformat()},
                 {"label": "2nd trimester", "start": (p.lmp + timedelta(weeks=14)).isoformat(),
                  "end": (p.lmp + timedelta(weeks=28)).isoformat()},
                 {"label": "3rd trimester", "start": (p.lmp + timedelta(weeks=28)).isoformat(), "end": end.isoformat()}]
        if p.delivery_date:
            bands.append({"label": "Postnatal (6 w)", "start": p.delivery_date.isoformat(),
                          "end": (p.delivery_date + timedelta(days=42)).isoformat()})
            markers.append({"date": p.delivery_date.isoformat(), "label": "Delivery"})
        else:
            markers.append({"date": p.edd.isoformat(), "label": "EDD"})
        markers.append({"date": p.lmp.isoformat(), "label": "LMP"})
    return {"lanes": LANES, "events": events, "bands": bands, "markers": markers}


def measurements(s: Session, pid: str) -> dict:
    out: dict[str, dict] = {}
    rows = s.execute(select(M.Observation, M.Visit).join(M.Visit, M.Visit.visit_id == M.Observation.visit_id)
                     .where(M.Observation.patient_id == pid).order_by(M.Observation.observed_on)).all()
    for o, v in rows:
        if o.value_num is None:
            continue
        display, unit, loinc = obs_display(o.code)
        out.setdefault(o.code, {"code": o.code, "display": display, "unit": unit, "loinc": loinc, "points": []})
        out[o.code]["points"].append({"date": o.observed_on.isoformat(), "value": o.value_num,
                                      "visit_type": v.visit_type, "ga_weeks": v.ga_weeks})
    return out


def documents(s: Session, pid: str) -> list[dict]:
    return [{"doc_id": d.doc_id, "doc_type": d.doc_type, "title": d.title, "date": d.doc_date.isoformat(),
             "author": d.author, "source": d.source_system}
            for d in s.scalars(select(M.Document).where(M.Document.patient_id == pid).order_by(M.Document.doc_date.desc()))]


def _iso(d):
    return d.isoformat() if d else None
