"""EXTRACT: read every clinic source into harmonised *staging* DataFrames.

Supported sources ("meet the clinic where it is"):
  * EHR / HMIS CSV exports  (folder with patients.csv, encounters.csv, ...)
  * Excel ANC registers      (wide: one row per pregnancy, ANC1..ANC5 columns)
  * PDF lab / imaging reports (text PDFs; scanned images -> add OCR, see docs)
  * Free-text notes          (JSONL)

Values stay as raw strings here; typing and coding happen in clean/normalize.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

STAGING_TABLES = ["patients", "pregnancies", "encounters", "observations", "labs", "appointments", "children",
                  "immunizations", "documents"]


@dataclass
class Staging:
    frames: dict[str, list[pd.DataFrame]] = field(default_factory=lambda: {t: [] for t in STAGING_TABLES})
    source_stats: list[dict] = field(default_factory=list)

    def add(self, table: str, df: pd.DataFrame) -> None:
        if len(df):
            self.frames[table].append(df)

    def get(self, table: str) -> pd.DataFrame:
        parts = self.frames[table]
        return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()


def _csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, dtype=str, keep_default_na=False)


# ----------------------------------------------------------------------------- EHR export
def extract_ehr_export(folder: Path, facility_id: str, st: Staging) -> None:
    src = f"ehr_export:{facility_id}"
    p = _csv(folder / "patients.csv")
    st.add("patients", pd.DataFrame({
        "source_system": src, "facility_id": facility_id, "source_id": p["mrn"], "rch_id": p["rch_id"],
        "name": p["patient_name"], "age": p["age"], "phone": p["mobile"], "email": p["email"],
        "language": p["preferred_language"], "village": p["village"], "district": p["district"],
        "caregiver_name": p["caregiver_name"], "caregiver_relation": p["caregiver_relation"],
        "caregiver_phone": p["caregiver_mobile"], "consent_sms": p["consent_sms"],
        "consent_whatsapp": p["consent_whatsapp"], "consent_email": p["consent_email"],
        "registered_on": p["registered_on"]}))
    pr = _csv(folder / "pregnancies.csv")
    st.add("pregnancies", pd.DataFrame({
        "source_system": src, "source_patient_id": pr["mrn"], "source_episode_id": pr["episode_id"],
        "lmp": pr["lmp"], "edd": pr["edd"], "gravida": pr["gravida"], "parity": pr["parity"],
        "registered_on": pr["registered_on"], "delivery_date": pr["delivery_date"],
        "delivery_mode": pr["delivery_mode"],
        "delivery_facility_id": pr["delivery_date"].map(lambda v: facility_id if v else "")}))
    e = _csv(folder / "encounters.csv")
    st.add("encounters", pd.DataFrame({
        "source_system": src, "facility_id": facility_id, "source_encounter_id": e["encounter_id"],
        "source_patient_id": e["mrn"], "source_episode_id": e["episode_id"], "source_child_id": e["child_mrn"],
        "date": e["encounter_date"], "type_raw": e["encounter_type"], "status_raw": e["status"],
        "provider_id": e["provider_id"]}))
    o = _csv(folder / "observations.csv")
    st.add("observations", pd.DataFrame({
        "source_system": src, "source_encounter_id": o["encounter_id"], "source_patient_id": o["mrn"],
        "name_raw": o["obs_name"], "value_raw": o["value"], "unit_raw": o["unit"], "date": o["obs_date"]}))
    lab = _csv(folder / "lab_orders.csv")
    st.add("labs", pd.DataFrame({
        "source_system": src, "source_order_id": lab["order_id"], "source_encounter_id": lab["encounter_id"],
        "source_patient_id": lab["mrn"], "test_raw": lab["test_name"], "ordered_on": lab["ordered_on"],
        "resulted_on": lab["resulted_on"], "result": lab["result"], "report_doc_id": ""}))
    a = _csv(folder / "appointments.csv")
    st.add("appointments", pd.DataFrame({
        "source_system": src, "facility_id": facility_id, "source_appt_id": a["appointment_id"],
        "source_patient_id": a["mrn"], "source_child_id": a["child_mrn"],
        "source_encounter_id": a["booked_from_encounter"], "purpose_raw": a["purpose"], "due": a["due_date"]}))
    ch = _csv(folder / "children.csv")
    st.add("children", pd.DataFrame({
        "source_system": src, "facility_id": facility_id, "source_child_id": ch["child_mrn"],
        "source_mother_id": ch["mother_mrn"], "source_episode_id": ch["episode_id"], "name": ch["child_name"],
        "sex": ch["sex"], "dob": ch["dob"], "birth_weight_g": ch["birth_weight_g"]}))
    im = _csv(folder / "immunizations.csv")
    st.add("immunizations", pd.DataFrame({
        "source_system": src, "source_child_id": im["child_mrn"], "vaccine": im["vaccine"],
        "schedule": im["schedule"], "due": im["due_date"], "given": im["given_date"]}))
    docs = []
    notes_path = folder / "notes.jsonl"
    if notes_path.exists():
        for line in notes_path.read_text(encoding="utf-8").splitlines():
            n = json.loads(line)
            docs.append({"source_system": src, "facility_id": facility_id, "source_doc_id": n["note_id"],
                         "source_encounter_id": n["encounter_id"], "source_patient_id": n["mrn"],
                         "source_child_id": n["child_mrn"], "doc_type": n["note_type"], "title": n["title"],
                         "doc_date": n["note_date"], "author": n["author"], "text": n["text"],
                         "source_file": f"{folder.name}/notes.jsonl"})
    st.add("documents", pd.DataFrame(docs))
    st.source_stats.append({"source": src, "type": "EHR CSV export", "files": len(list(folder.iterdir())),
                            "rows": {"patients": len(p), "encounters": len(e), "observations": len(o),
                                     "lab_orders": len(lab), "appointments": len(a), "notes": len(docs)}})


# ----------------------------------------------------------------------------- Excel register
def extract_excel_register(xlsx: Path, facility_id: str, facility_name: str, st: Staging) -> None:
    """Melt a wide ANC register into long staging tables."""
    src = f"excel_register:{facility_id}"
    df = pd.read_excel(xlsx, dtype=object)
    df.columns = [str(c).strip() for c in df.columns]
    pats, pregs, encs, obs, appts, children, docs = [], [], [], [], [], [], []
    for _, r in df.iterrows():
        sl = str(r.get("Sl. No.")).split(".")[0]
        pid = f"{facility_id}-R{sl}"
        rch = "" if pd.isna(r.get("RCH ID")) else str(r.get("RCH ID")).split(".")[0]
        mobile = r.get("Mobile No.")
        pats.append({"source_system": src, "facility_id": facility_id, "source_id": pid, "rch_id": rch,
                     "name": r.get("Name of PW"), "age": r.get("Age"), "phone": mobile, "email": "",
                     "language": r.get("Language", ""), "village": r.get("Village"), "district": "",
                     "caregiver_name": r.get("Husband/Caregiver Name"), "caregiver_relation": r.get("Relation"),
                     "caregiver_phone": "", "consent_sms": "Y" if not pd.isna(mobile) else "N",
                     "consent_whatsapp": "N", "consent_email": "N", "registered_on": r.get("Reg. Date")})
        place = r.get("Place of Delivery")
        delivered_here = isinstance(place, str) and place.strip().lower() == facility_name.lower()
        pregs.append({"source_system": src, "source_patient_id": pid, "source_episode_id": f"{pid}-EP",
                      "lmp": r.get("LMP"), "edd": r.get("EDD"), "gravida": r.get("Gravida"), "parity": r.get("Para"),
                      "registered_on": r.get("Reg. Date"), "delivery_date": r.get("Delivery Date"),
                      "delivery_mode": r.get("Type of Delivery"),
                      "delivery_facility_id": facility_id if delivered_here else ""})
        for j in range(1, 10):
            col = f"ANC{j} Date"
            if col not in df.columns:
                break
            if pd.isna(r.get(col)):
                continue
            eid = f"{pid}-ANC{j}"
            encs.append({"source_system": src, "facility_id": facility_id, "source_encounter_id": eid,
                         "source_patient_id": pid, "source_episode_id": f"{pid}-EP", "source_child_id": "",
                         "date": r.get(col), "type_raw": "ANC", "status_raw": "Completed", "provider_id": ""})
            for field_name, label in ((f"ANC{j} Wt (kg)", "Wt"), (f"ANC{j} BP", "BP"), (f"ANC{j} Hb", "Hb")):
                if field_name in df.columns and not pd.isna(r.get(field_name)):
                    obs.append({"source_system": src, "source_encounter_id": eid, "source_patient_id": pid,
                                "name_raw": label, "value_raw": str(r.get(field_name)), "unit_raw": "",
                                "date": r.get(col)})
        if delivered_here and not pd.isna(r.get("Delivery Date")):
            eid = f"{pid}-DEL"
            encs.append({"source_system": src, "facility_id": facility_id, "source_encounter_id": eid,
                         "source_patient_id": pid, "source_episode_id": f"{pid}-EP", "source_child_id": "",
                         "date": r.get("Delivery Date"), "type_raw": "Delivery", "status_raw": "Completed",
                         "provider_id": ""})
            if not pd.isna(r.get("Baby Sex")):
                children.append({"source_system": src, "facility_id": facility_id, "source_child_id": f"{pid}-B",
                                 "source_mother_id": pid, "source_episode_id": f"{pid}-EP",
                                 "name": f"Baby of {str(r.get('Name of PW')).split(' ')[0]}", "sex": r.get("Baby Sex"),
                                 "dob": r.get("Delivery Date"), "birth_weight_g": r.get("Birth Wt (gm)")})
        for j in range(1, 4):
            col = f"PNC{j} Date"
            if col in df.columns and not pd.isna(r.get(col)):
                encs.append({"source_system": src, "facility_id": facility_id, "source_encounter_id": f"{pid}-PNC{j}",
                             "source_patient_id": pid, "source_episode_id": f"{pid}-EP", "source_child_id": "",
                             "date": r.get(col), "type_raw": "PNC", "status_raw": "Completed", "provider_id": ""})
        if not pd.isna(r.get("Next Due Date")):
            appts.append({"source_system": src, "facility_id": facility_id, "source_appt_id": f"{pid}-NEXT",
                          "source_patient_id": pid, "source_child_id": "", "source_encounter_id": "",
                          "purpose_raw": "Next due (register)", "due": r.get("Next Due Date")})
        if not pd.isna(r.get("Remarks")):
            docs.append({"source_system": src, "facility_id": facility_id, "source_doc_id": f"{pid}-REM",
                         "source_encounter_id": "", "source_patient_id": pid, "source_child_id": "",
                         "doc_type": "register_remark", "title": "ANC register remarks",
                         "doc_date": r.get("Reg. Date"), "author": "ANM (register)",
                         "text": f"Register remarks for {r.get('Name of PW')}: {r.get('Remarks')}",
                         "source_file": xlsx.name})
    for name, rows in (("patients", pats), ("pregnancies", pregs), ("encounters", encs), ("observations", obs),
                       ("appointments", appts), ("children", children), ("documents", docs)):
        st.add(name, pd.DataFrame(rows))
    st.source_stats.append({"source": src, "type": "Excel ANC register (wide)", "files": 1,
                            "rows": {"register_rows": len(df), "encounters_melted": len(encs),
                                     "observations_melted": len(obs)}})


# ----------------------------------------------------------------------------- PDF reports
_LINE = re.compile(r"^(?P<test>[^|]+)\|(?P<result>[^|]+)\|(?P<rep>.+)$")


def extract_lab_pdfs(folder: Path, facility_id: str, st: Staging) -> None:
    """Parse text PDFs (Lab No / RCH ID / Sample Date / 'Test | Result | Reported on' lines)."""
    from pypdf import PdfReader

    src = f"pdf_reports:{facility_id}"
    labs, docs, failed = [], [], 0
    for pdf in sorted(folder.glob("*.pdf")):
        try:
            text = "\n".join(page.extract_text() or "" for page in PdfReader(pdf).pages)
        except Exception:  # corrupt / scanned PDF -> needs OCR
            failed += 1
            continue
        rch = re.search(r"RCH ID:\s*(\d+)", text)
        sample = re.search(r"Sample Date:\s*([\d/]+)", text)
        if not (rch and sample):
            failed += 1
            continue
        doc_id = f"DOC-{pdf.stem}"
        docs.append({"source_system": src, "facility_id": facility_id, "source_doc_id": doc_id,
                     "source_encounter_id": "", "source_patient_id": f"rch:{rch.group(1)}", "source_child_id": "",
                     "doc_type": "lab_report", "title": "Laboratory / imaging report", "doc_date": sample.group(1),
                     "author": "Laboratory", "text": text.strip(), "source_file": f"lab_reports/{pdf.name}"})
        started = False
        for i, line in enumerate(text.splitlines()):
            if line.startswith("Test | Result"):
                started = True
                continue
            m = _LINE.match(line.strip()) if started else None
            if not m:
                continue
            result = m.group("result").strip()
            rep = m.group("rep").strip()
            labs.append({"source_system": src, "source_order_id": f"{pdf.stem}-{i}", "source_encounter_id": "",
                         "source_patient_id": f"rch:{rch.group(1)}", "test_raw": m.group("test").strip(),
                         "ordered_on": sample.group(1), "resulted_on": "" if rep == "-" else rep,
                         "result": "" if result.lower().startswith("result awaited") else result,
                         "report_doc_id": doc_id})
    st.add("labs", pd.DataFrame(labs))
    st.add("documents", pd.DataFrame(docs))
    st.source_stats.append({"source": src, "type": "PDF lab/imaging reports", "files": len(docs) + failed,
                            "rows": {"parsed_reports": len(docs), "lab_lines": len(labs), "unparsed_files": failed}})


def extract_all(raw_dir: Path) -> Staging:
    st = Staging()
    facilities = pd.read_csv(raw_dir / "facilities.csv", dtype=str)
    for _, f in facilities.iterrows():
        fid = f["facility_id"]
        if f["source_system"] == "ehr_export" and (raw_dir / f"ehr_{fid}").exists():
            extract_ehr_export(raw_dir / f"ehr_{fid}", fid, st)
        elif f["source_system"] == "excel_register" and (raw_dir / f"register_{fid}").exists():
            folder = raw_dir / f"register_{fid}"
            for xlsx in folder.glob("*.xlsx"):
                extract_excel_register(xlsx, fid, f["name"], st)
            if (folder / "lab_reports").exists():
                extract_lab_pdfs(folder / "lab_reports", fid, st)
    return st
