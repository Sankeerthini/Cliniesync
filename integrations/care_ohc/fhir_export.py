"""Export a ClinieSync patient as a FHIR R4 `collection` Bundle.

FHIR is the interoperability contract between ClinieSync's unified layer and
EMRs such as OHC CARE (or any FHIR server / ABDM-aligned system). Mapping:

  patients        -> Patient            (identifier: ClinieSync ID + RCH ID)
  pregnancies     -> EpisodeOfCare      (type: antenatal care)
  visits          -> Encounter          (status finished / cancelled for no-show)
  observations    -> Observation        (LOINC-coded where known: 718-7, 29463-7, 8480-6, 8462-4, 11881-0, 55283-6)
  investigations  -> ServiceRequest (+ DiagnosticReport when resulted)
  followups       -> Appointment        (status proposed / booked / fulfilled / noshow)
  documents       -> DocumentReference  (text attachment)

    python -m integrations.care_ohc.fhir_export CS-000010 > bundle.json
"""
from __future__ import annotations

import base64
import json
import sys

from sqlalchemy import select

from database import models as M
from database.session import session_scope

SYS_ID = "https://cliniesync.example.org/fhir/patient-id"   # placeholder namespace for the hackathon
SYS_RCH = "https://rch.nhm.gov.in/rch-id"                    # Reproductive & Child Health ID (synthetic values)
LOINC = "http://loinc.org"
APPT_STATUS = {"completed": "fulfilled", "missed": "noshow", "overdue": "booked", "due": "booked",
               "upcoming": "booked", "cancelled": "cancelled"}


def _ref(kind: str, rid: str) -> dict:
    return {"reference": f"{kind}/{rid}"}


def patient_bundle(patient_id: str) -> dict:
    with session_scope() as s:
        p = s.get(M.Patient, patient_id)
        if not p:
            raise KeyError(patient_id)
        entries = []

        def add(res: dict):
            entries.append({"fullUrl": f"urn:uuid:{res['resourceType']}-{res['id']}", "resource": res})

        ids = [{"system": SYS_ID, "value": p.patient_id}] + ([{"system": SYS_RCH, "value": p.rch_id}] if p.rch_id else [])
        add({"resourceType": "Patient", "id": p.patient_id, "identifier": ids, "gender": "female",
             "name": [{"text": p.full_name}],
             "telecom": [{"system": "phone", "value": p.phone, "use": "mobile"}] if p.phone else [],
             "address": [{"text": ", ".join(x for x in (p.village, p.district) if x)}],
             "communication": [{"language": {"coding": [{"system": "urn:ietf:bcp:47", "code": p.preferred_language}]},
                                "preferred": True}],
             "contact": [{"relationship": [{"text": p.caregiver_relation}], "name": {"text": p.caregiver_name},
                          "telecom": [{"system": "phone", "value": p.caregiver_phone}]}] if p.caregiver_name else []})
        for pr in s.scalars(select(M.Pregnancy).where(M.Pregnancy.patient_id == patient_id)):
            add({"resourceType": "EpisodeOfCare", "id": pr.pregnancy_id,
                 "status": "active" if pr.status in ("antenatal", "delivered") else "finished",
                 "type": [{"text": "Antenatal and postnatal care"}], "patient": _ref("Patient", patient_id),
                 "period": {"start": pr.lmp.isoformat(), **({"end": pr.delivery_date.isoformat()} if pr.delivery_date else {})},
                 "extension": [{"url": "https://cliniesync.example.org/fhir/edd", "valueDate": pr.edd.isoformat()}]})
        for v in s.scalars(select(M.Visit).where(M.Visit.patient_id == patient_id)):
            add({"resourceType": "Encounter", "id": v.visit_id, "status": "finished" if v.status == "completed" else "cancelled",
                 "class": {"system": "http://terminology.hl7.org/CodeSystem/v3-ActCode", "code": "AMB"},
                 "type": [{"text": v.visit_type}], "subject": _ref("Patient", patient_id),
                 **({"episodeOfCare": [_ref("EpisodeOfCare", v.pregnancy_id)]} if v.pregnancy_id else {}),
                 "period": {"start": v.visit_date.isoformat()}, "serviceProvider": {"display": v.facility_id}})
        for o in s.scalars(select(M.Observation).where(M.Observation.patient_id == patient_id)):
            res = {"resourceType": "Observation", "id": f"obs-{o.obs_id}", "status": "final",
                   "code": {"coding": [{"system": LOINC, "code": o.loinc, "display": o.display}] if o.loinc else [],
                            "text": o.display},
                   "subject": _ref("Patient", patient_id), "encounter": _ref("Encounter", o.visit_id),
                   "effectiveDateTime": o.observed_on.isoformat()}
            if o.value_num is not None:
                res["valueQuantity"] = {"value": o.value_num, "unit": o.unit}
            else:
                res["valueString"] = o.value_text
            add(res)
        for i in s.scalars(select(M.Investigation).where(M.Investigation.patient_id == patient_id)):
            add({"resourceType": "ServiceRequest", "id": i.investigation_id,
                 "status": "completed" if i.status == "resulted" else "active", "intent": "order",
                 "code": {"text": i.test_name}, "subject": _ref("Patient", patient_id),
                 **({"encounter": _ref("Encounter", i.visit_id)} if i.visit_id else {}),
                 "authoredOn": i.ordered_on.isoformat()})
            if i.status == "resulted":
                add({"resourceType": "DiagnosticReport", "id": f"dr-{i.investigation_id}", "status": "final",
                     "code": {"text": i.test_name}, "subject": _ref("Patient", patient_id),
                     "basedOn": [_ref("ServiceRequest", i.investigation_id)], "issued": f"{i.resulted_on.isoformat()}T00:00:00Z",
                     "conclusion": i.result_summary})
        for f in s.scalars(select(M.FollowUp).where(M.FollowUp.patient_id == patient_id)):
            add({"resourceType": "Appointment", "id": f.followup_id, "status": APPT_STATUS.get(f.status, "proposed"),
                 "serviceType": [{"text": f.followup_type}], "description": f.description,
                 "start": f"{f.due_on.isoformat()}T09:00:00+05:30",
                 "participant": [{"actor": _ref("Patient", patient_id), "status": "needs-action"}]})
        for d in s.scalars(select(M.Document).where(M.Document.patient_id == patient_id)):
            add({"resourceType": "DocumentReference", "id": d.doc_id, "status": "current", "type": {"text": d.doc_type},
                 "subject": _ref("Patient", patient_id), "date": f"{d.doc_date.isoformat()}T00:00:00Z",
                 "description": d.title,
                 "content": [{"attachment": {"contentType": "text/plain",
                                             "data": base64.b64encode(d.text.encode()).decode()}}]})
        return {"resourceType": "Bundle", "type": "collection", "entry": entries}


if __name__ == "__main__":
    print(json.dumps(patient_bundle(sys.argv[1] if len(sys.argv) > 1 else "CS-000010"), indent=1))
