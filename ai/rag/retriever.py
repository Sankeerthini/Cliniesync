"""Hybrid patient retrieval: structured facts (SQL) + unstructured notes (vector search).

Produces an *evidence pack* - a numbered list of source items [S1], [S2], ...
Every sentence the summariser writes must cite these ids, and the UI lets the
user open each source. Content is filtered by the caller's data scopes
(minimum-necessary principle): coordinators see visits and follow-ups but not
clinical values or notes.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from database import models as M


@dataclass
class EvidenceItem:
    id: str
    kind: str            # profile / pregnancy / visit / investigation / followup / child / immunization / note
    date: date | None
    title: str
    text: str
    ref_type: str
    ref_id: str

    def as_dict(self) -> dict:
        return {"id": self.id, "kind": self.kind, "date": self.date.isoformat() if self.date else None,
                "title": self.title, "text": self.text, "ref_type": self.ref_type, "ref_id": self.ref_id}


@dataclass
class Evidence:
    patient: M.Patient
    pregnancies: list[M.Pregnancy]
    visits: list[M.Visit]
    observations: dict[str, list[M.Observation]]
    investigations: list[M.Investigation]
    followups: list[M.FollowUp]
    children: list[M.Child]
    immunizations: list[M.Immunization]
    notes: list[dict]
    facility_names: dict[str, str]
    items: list[EvidenceItem] = field(default_factory=list)

    def blob(self) -> str:
        return "\n".join(f"[{i.id}] {i.title}: {i.text}" for i in self.items)

    def ids(self) -> set[str]:
        return {i.id for i in self.items}

    def find(self, ref_type: str, ref_id: str) -> str | None:
        for i in self.items:
            if i.ref_type == ref_type and i.ref_id == ref_id:
                return i.id
        return None


def fmt_d(d: date | None) -> str:
    return d.strftime("%d %b %Y") if d else "-"


def _vitals_text(obs: list[M.Observation]) -> str:
    by = {o.code: o for o in obs}
    parts = []
    if "weight" in by:
        parts.append(f"weight {by['weight'].value_num:g} kg")
    if "bp_systolic" in by and "bp_diastolic" in by:
        parts.append(f"BP {by['bp_systolic'].value_num:g}/{by['bp_diastolic'].value_num:g} mmHg")
    if "hemoglobin" in by:
        parts.append(f"Hb {by['hemoglobin'].value_num:g} g/dL")
    if "fundal_height" in by:
        parts.append(f"fundal height {by['fundal_height'].value_num:g} cm")
    if "fetal_heart_rate" in by:
        parts.append(f"FHR {by['fetal_heart_rate'].value_num:g}/min")
    if "infant_weight" in by:
        parts.append(f"infant weight {by['infant_weight'].value_num:g} kg")
    if "urine_albumin" in by:
        parts.append(f"urine albumin {by['urine_albumin'].value_text}")
    return ", ".join(parts)


def load_evidence(s: Session, patient_id: str, scopes: set[str], question: str = "", note_k: int = 6) -> Evidence | None:
    p = s.get(M.Patient, patient_id)
    if not p:
        return None
    fac = {f.facility_id: f.name for f in s.scalars(select(M.Facility))}
    preg = list(s.scalars(select(M.Pregnancy).where(M.Pregnancy.patient_id == patient_id).order_by(M.Pregnancy.lmp)))
    visits = list(s.scalars(select(M.Visit).where(M.Visit.patient_id == patient_id).order_by(M.Visit.visit_date)))
    obs: dict[str, list[M.Observation]] = {}
    for o in s.scalars(select(M.Observation).where(M.Observation.patient_id == patient_id)):
        obs.setdefault(o.visit_id, []).append(o)
    inv = list(s.scalars(select(M.Investigation).where(M.Investigation.patient_id == patient_id)
                         .order_by(M.Investigation.ordered_on)))
    fus = list(s.scalars(select(M.FollowUp).where(M.FollowUp.patient_id == patient_id).order_by(M.FollowUp.due_on)))
    kids = list(s.scalars(select(M.Child).where(M.Child.mother_patient_id == patient_id)))
    imms = list(s.scalars(select(M.Immunization).where(M.Immunization.child_id.in_([k.child_id for k in kids]))
                          .order_by(M.Immunization.due_on))) if kids else []
    notes = []
    if "notes" in scopes:
        notes = retrieve_notes(patient_id, question or "pregnancy visit summary follow-up", k=note_k)
    ev = Evidence(p, preg, visits, obs, inv, fus, kids, imms, notes, fac)
    _number(ev, scopes)
    return ev


def retrieve_notes(patient_id: str, query: str, k: int = 6) -> list[dict]:
    from ai.rag.vector_store import get_vector_store

    from database.session import session_scope

    try:
        hits = get_vector_store().query(query, k=k, where={"patient_id": patient_id})
    except Exception:
        return []
    # Defence in depth: never trust the index alone for patient ownership (it can be stale after a re-load).
    with session_scope() as s:
        owned = {d.doc_id for d in s.scalars(select(M.Document).where(
            M.Document.doc_id.in_([h.metadata.get("doc_id") for h in hits]), M.Document.patient_id == patient_id))}
    return [{"chunk_id": h.id, "doc_id": h.metadata.get("doc_id"), "title": h.metadata.get("title"),
             "doc_type": h.metadata.get("doc_type"), "doc_date": h.metadata.get("doc_date"), "text": h.text,
             "score": round(h.score, 3)} for h in hits if h.metadata.get("doc_id") in owned]


def _number(ev: Evidence, scopes: set[str]) -> None:
    items: list[EvidenceItem] = []

    def add(kind, d, title, text, ref_type, ref_id):
        items.append(EvidenceItem(f"S{len(items) + 1}", kind, d, title, text, ref_type, ref_id))

    p = ev.patient
    contact = f"; phone {p.phone}; caregiver {p.caregiver_name} ({p.caregiver_relation})" if "contact" in scopes else ""
    add("profile", p.registered_on, "Patient profile",
        f"{p.full_name} ({p.patient_id}), {p.age_years} y, preferred language {p.preferred_language}, "
        f"registered at {ev.facility_names.get(p.facility_id)}{contact}", "patient", p.patient_id)
    for pr in ev.pregnancies:
        txt = (f"G{pr.gravida}P{pr.parity}; LMP {fmt_d(pr.lmp)}; EDD {fmt_d(pr.edd)}; registered {fmt_d(pr.registration_date)}"
               f" at {pr.registration_ga_weeks} weeks; status {pr.status.replace('_', ' ')}")
        if pr.delivery_date:
            txt += f"; delivered {fmt_d(pr.delivery_date)}" + (f" ({pr.delivery_mode}, as documented)" if pr.delivery_mode else "")
        add("pregnancy", pr.registration_date, "Pregnancy episode", txt, "pregnancy", pr.pregnancy_id)
    for v in ev.visits:
        txt = f"{v.visit_type} at {ev.facility_names.get(v.facility_id)}" + (f", GA {v.ga_weeks} w" if v.ga_weeks else "")
        if v.status == "no_show":
            txt += " - documented as NO-SHOW"
        elif "clinical_values" in scopes and ev.observations.get(v.visit_id):
            txt += "; recorded: " + _vitals_text(ev.observations[v.visit_id])
        add("visit", v.visit_date, f"Visit {fmt_d(v.visit_date)}", txt, "visit", v.visit_id)
    for i in ev.investigations:
        txt = f"{i.test_name} ordered {fmt_d(i.ordered_on)}; " + (
            f"resulted {fmt_d(i.resulted_on)}" if i.status == "resulted" else "no result documented yet")
        if "clinical_values" in scopes and i.result_summary:
            txt += f"; documented result: {i.result_summary}"
        add("investigation", i.ordered_on, f"Investigation - {i.test_name}", txt, "investigation", i.investigation_id)
    for c in ev.children:
        add("child", c.dob, "Child", f"{c.full_name} ({c.child_id}), {c.sex}, born {fmt_d(c.dob)}, birth weight "
            f"{c.birth_weight_g} g", "child", c.child_id)
    if ev.immunizations:
        sessions: dict[str, list[M.Immunization]] = {}
        for im in ev.immunizations:
            sessions.setdefault(im.schedule_label, []).append(im)
        for label, ims in sessions.items():
            given = [im for im in ims if im.given_on]
            status = f"given {fmt_d(given[0].given_on)}" if given else f"not documented (due {fmt_d(ims[0].due_on)})"
            add("immunization", ims[0].due_on, f"Immunization {label}",
                f"{', '.join(im.vaccine for im in ims)}: {status}", "immunization", ims[0].imm_id)
    for f in ev.followups:
        add("followup", f.due_on, f"Follow-up - {f.followup_type}",
            f"due {fmt_d(f.due_on)}; status {f.status}" + (f" (completed {fmt_d(f.completed_on)})" if f.completed_on else "")
            + f"; documented instruction: \"{f.description}\"", "followup", f.followup_id)
    for n in ev.notes:
        add("note", date.fromisoformat(n["doc_date"]) if n.get("doc_date") else None, n["title"], n["text"],
            "document", n["doc_id"])
    ev.items = items
