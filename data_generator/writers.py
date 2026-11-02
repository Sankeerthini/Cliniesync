"""Serialise the simulated cohort into the formats clinics really hold.

Facilities F1 and F2 -> "EHR export" folders (CSV + JSONL notes) with typical
real-world noise: mixed date formats, local test names, combined BP strings,
unit variants (g%, grams), duplicated rows, a few typos and missing IDs.

Facility F3 -> a wide Excel ANC register (one row per pregnancy, ANC1..ANC5
columns) plus PDF lab reports - i.e. no EHR at all.

This deliberately makes the ETL do real work (melt, parse, normalise, link).
"""
from __future__ import annotations

import json
import random
from collections import defaultdict
from datetime import date
from pathlib import Path

import pandas as pd

from data_generator.reference import FACILITIES, OBS_CODES, PROVIDERS, TESTS
from data_generator.simulate import Cohort

FAC = {f["facility_id"]: f for f in FACILITIES}

OBS_LOCAL_NAMES = {
    "weight": ["Wt", "Weight", "WEIGHT (kg)"],
    "hemoglobin": ["Hb", "HB", "Haemoglobin"],
    "fundal_height": ["FH", "Fundal Ht"],
    "fetal_heart_rate": ["FHR", "FHS"],
    "urine_albumin": ["Urine Albumin", "Urine alb"],
    "infant_weight": ["Baby Wt", "Infant weight"],
}
ENC_TYPE_NAMES = {
    "ANC": ["ANC", "Antenatal visit", "ANC Follow-up"],
    "Delivery": ["Delivery", "IP - Delivery"],
    "PNC": ["PNC", "Postnatal visit"],
    "Child": ["Immunisation", "Immunization clinic"],
}
APPT_PURPOSE_NAMES = {
    "ANC visit": ["Next ANC", "ANC follow up", "ANC review"],
    "Report review": ["Lab report review", "Review with reports"],
    "PNC visit": ["PNC check", "Postnatal check"],
    "Immunization": ["Immunisation due", "Vaccination due"],
}


class _Noise:
    def __init__(self, rng: random.Random):
        self.r = rng

    def date(self, d: date | None, style: str = "mixed") -> str:
        if d is None:
            return ""
        r = self.r.random()
        if style == "iso" and r < .85:
            return d.isoformat()
        if r < .45:
            return d.strftime("%d/%m/%Y")
        if r < .75:
            return d.isoformat()
        return d.strftime("%d-%b-%Y")

    def name(self, s: str) -> str:
        r = self.r.random()
        if r < .15:
            return s.upper()
        if r < .25:
            return "  " + s.lower() + " "
        return s

    def phone(self, s: str | None) -> str:
        if not s:
            return ""
        digits = s[-10:]
        r = self.r.random()
        if r < .35:
            return f"+91 {digits[:5]} {digits[5:]}"
        if r < .65:
            return "0" + digits
        return digits


def _write_ehr(c: Cohort, fac: str, out: Path, rng: random.Random) -> dict:
    nz = _Noise(rng)
    style = "iso" if fac == "F1" else "mixed"
    out.mkdir(parents=True, exist_ok=True)
    encs = [e for e in c.encounters if e["facility_id"] == fac]
    enc_ids = {e["enc_id"] for e in encs}
    keys = {e["key"] for e in encs}
    pat_by_key = {p["key"]: p for p in c.patients}
    mrn = {k: f"{fac}-{i:05d}" for i, k in enumerate(sorted(keys), 1)}
    child_keys = {e["child_key"] for e in encs if e["child_key"]} | {
        ch["child_key"] for ch in c.children if ch["facility_id"] == fac}
    child_mrn = {k: f"{fac}-C{i:04d}" for i, k in enumerate(sorted(child_keys), 1)}

    # patients
    rows = []
    for k in sorted(keys):
        p = pat_by_key[k]
        rows.append({
            "mrn": mrn[k], "rch_id": "" if rng.random() < .1 else p["rch_id"], "patient_name": nz.name(p["name"]),
            "age": p["age"], "mobile": nz.phone(p["phone"]), "email": p["email"] or "",
            "preferred_language": {"kn": "Kannada", "hi": "Hindi", "bn": "Bengali", "en": "English"}[p["language"]],
            "village": p["village"], "district": p["district"], "caregiver_name": p["caregiver_name"],
            "caregiver_relation": p["caregiver_relation"], "caregiver_mobile": nz.phone(p["caregiver_phone"]),
            "consent_sms": "Y" if p["consent_sms"] else "N", "consent_whatsapp": "Y" if p["consent_whatsapp"] else "N",
            "consent_email": "Y" if p["consent_email"] else "N",
            "registered_on": nz.date(p["registered_on"], style),
        })
    pd.DataFrame(rows).to_csv(out / "patients.csv", index=False)

    # pregnancies (episodes)
    rows = []
    for pr in c.pregnancies:
        if pr["key"] not in keys:
            continue
        rows.append({"episode_id": f"{fac}-{pr['episode_id']}", "mrn": mrn[pr["key"]], "lmp": nz.date(pr["lmp"], style),
                     "edd": nz.date(pr["edd"], style), "gravida": pr["gravida"], "parity": pr["parity"],
                     "registered_on": nz.date(pr["reg_date"], style) if pat_by_key[pr["key"]]["facility_id"] == fac else "",
                     "delivery_date": nz.date(pr["delivery_date"], style) if pr["delivery_facility"] == fac else "",
                     "delivery_mode": pr["delivery_mode"] if pr["delivery_facility"] == fac else ""})
    pd.DataFrame(rows).to_csv(out / "pregnancies.csv", index=False)

    # encounters (+ ~1.5% duplicates)
    rows = []
    for e in encs:
        row = {"encounter_id": e["enc_id"], "mrn": mrn[e["key"]], "episode_id": f"{fac}-{e['episode_id']}",
               "child_mrn": child_mrn.get(e["child_key"], "") if e["child_key"] else "",
               "encounter_date": nz.date(e["date"], style), "encounter_type": rng.choice(ENC_TYPE_NAMES[e["category"]]),
               "status": ("Completed" if rng.random() < .7 else "Seen") if e["status"] == "completed"
               else rng.choice(["No-show", "DNA"]),
               "provider_id": e["provider_id"]}
        rows.append(row)
        if rng.random() < .015:
            rows.append(dict(row))
    pd.DataFrame(rows).to_csv(out / "encounters.csv", index=False)

    # observations (long format; BP combined for F1, split for F2)
    rows = []
    by_enc = defaultdict(dict)
    for o in c.observations:
        if o["enc_id"] in enc_ids:
            by_enc[o["enc_id"]][o["code"]] = o
    for enc_id, obs in by_enc.items():
        enc_key = next(iter(obs.values()))["key"]
        base = {"encounter_id": enc_id, "mrn": mrn[enc_key]}
        if "bp_systolic" in obs:
            s, d = obs["bp_systolic"]["value"], obs["bp_diastolic"]["value"]
            dt = nz.date(obs["bp_systolic"]["date"], style)
            if rng.random() < .004:
                s = s * 10  # typo -> should be quarantined
            if fac == "F1":
                rows.append({**base, "obs_name": "BP", "value": f"{s}/{d}", "unit": "mmHg", "obs_date": dt})
            else:
                rows.append({**base, "obs_name": "BP Systolic", "value": str(s), "unit": "mmHg", "obs_date": dt})
                rows.append({**base, "obs_name": "BP Diastolic", "value": str(d), "unit": "mmHg", "obs_date": dt})
        for code, o in obs.items():
            if code in ("bp_systolic", "bp_diastolic"):
                continue
            v, unit = o["value"], OBS_CODES[code][1] or ""
            val = str(v)
            if code == "weight":
                if rng.random() < .004:
                    val = str(v * 10)  # typo
                elif rng.random() < .3:
                    val, unit = f"{v} kg", ""
            elif code == "hemoglobin":
                unit = rng.choice(["g/dL", "g%", "g/dl"])
            elif code == "infant_weight" and rng.random() < .35:
                val, unit = str(int(v * 1000)), "g"
            elif code == "fetal_heart_rate" and rng.random() < .3:
                val, unit = f"{v}/min", ""
            rows.append({**base, "obs_name": rng.choice(OBS_LOCAL_NAMES[code]), "value": val, "unit": unit,
                         "obs_date": nz.date(o["date"], style)})
            if rng.random() < .01:
                rows.append(dict(rows[-1]))
    pd.DataFrame(rows).to_csv(out / "observations.csv", index=False)

    # lab orders
    rows = []
    for lab in c.labs:
        if lab["enc_id"] not in enc_ids:
            continue
        rows.append({"order_id": lab["order_id"], "encounter_id": lab["enc_id"], "mrn": mrn[lab["key"]],
                     "test_name": lab["local_name"], "ordered_on": nz.date(lab["ordered_on"], style),
                     "resulted_on": nz.date(lab["resulted_on"], style), "result": lab["result"] or ""})
    pd.DataFrame(rows).to_csv(out / "lab_orders.csv", index=False)

    # appointments
    rows = []
    for a in c.appointments:
        if a["src_enc"] not in enc_ids:
            continue
        purpose = rng.choice(APPT_PURPOSE_NAMES[a["purpose"]])
        if a["purpose"] in ("PNC visit", "Immunization"):
            purpose = f"{purpose} - {a['label'].replace('Immunization-', '').replace('PNC-', '')}"
        rows.append({"appointment_id": a["appt_id"], "mrn": mrn[a["key"]],
                     "child_mrn": child_mrn.get(a["child_key"], "") if a["child_key"] else "",
                     "booked_from_encounter": a["src_enc"], "purpose": purpose, "due_date": nz.date(a["due"], style)})
    pd.DataFrame(rows).to_csv(out / "appointments.csv", index=False)

    # children + immunizations
    rows = []
    for ch in c.children:
        if ch["child_key"] in child_mrn:
            rows.append({"child_mrn": child_mrn[ch["child_key"]], "mother_mrn": mrn.get(ch["mother_key"], ""),
                         "episode_id": f"{fac}-{ch['episode_id']}", "child_name": ch["name"], "sex": ch["sex"],
                         "dob": nz.date(ch["dob"], style), "birth_weight_g": ch["birth_weight_g"]})
    pd.DataFrame(rows).to_csv(out / "children.csv", index=False)
    rows = [{"child_mrn": child_mrn[i["child_key"]], "vaccine": i["vaccine"], "schedule": i["schedule"],
             "due_date": nz.date(i["due"], style), "given_date": nz.date(i["given"], style)}
            for i in c.immunizations if i["child_key"] in child_mrn]
    pd.DataFrame(rows).to_csv(out / "immunizations.csv", index=False)

    # free-text notes
    with open(out / "notes.jsonl", "w", encoding="utf-8") as fh:
        for n in c.notes:
            if n["enc_id"] in enc_ids:
                fh.write(json.dumps({"note_id": n["note_id"], "encounter_id": n["enc_id"], "mrn": mrn[n["key"]],
                                     "child_mrn": child_mrn.get(n["child_key"], "") if n["child_key"] else "",
                                     "note_type": n["type"], "title": n["title"], "note_date": n["date"].isoformat(),
                                     "author": n["author"], "text": n["text"]}, ensure_ascii=False) + "\n")
    return {"facility": fac, "patients": len(keys), "encounters": len(encs)}


def _write_register(c: Cohort, fac: str, out: Path, rng: random.Random) -> dict:
    """Wide ANC register (Excel) + PDF lab reports for a facility without an EHR."""
    out.mkdir(parents=True, exist_ok=True)
    (out / "lab_reports").mkdir(exist_ok=True)

    def regdate(d: date | None):
        if d is None:
            return None
        r = rng.random()
        if r < .4:
            return d  # real Excel date cell
        if r < .7:
            return d.strftime("%d/%m/%Y")
        if r < .85:
            return d.strftime("%d.%m.%Y")
        return d.strftime("%d-%b-%y")

    pats = {p["key"]: p for p in c.patients if p["facility_id"] == fac}
    encs_by_key = defaultdict(list)
    for e in c.encounters:
        if e["key"] in pats:
            encs_by_key[e["key"]].append(e)
    obs_by_enc = defaultdict(dict)
    for o in c.observations:
        obs_by_enc[o["enc_id"]][o["code"]] = o["value"]
    appts_by_key = defaultdict(list)
    for a in c.appointments:
        if a["key"] in pats and a["facility_id"] == fac:
            appts_by_key[a["key"]].append(a)
    labs_by_enc = defaultdict(list)
    for lab in c.labs:
        if lab["facility_id"] == fac:
            labs_by_enc[lab["enc_id"]].append(lab)

    rows = []
    n_pdf = 0
    for i, pr in enumerate([p for p in c.pregnancies if p["key"] in pats], 1):
        p = pats[pr["key"]]
        row = {"Sl. No.": i, "RCH ID": p["rch_id"], "Name of PW": p["name"],
               "Husband/Caregiver Name": p["caregiver_name"], "Relation": p["caregiver_relation"],
               "Age": p["age"], "Mobile No.": p["phone"][-10:], "Village": p["village"],
               "Language": {"kn": "Kannada", "hi": "Hindi", "bn": "Bengali", "en": "English"}[p["language"]],
               "LMP": regdate(pr["lmp"]), "EDD": regdate(pr["edd"]), "Gravida": pr["gravida"], "Para": pr["parity"],
               "Reg. Date": regdate(pr["reg_date"])}
        anc = sorted([e for e in encs_by_key[pr["key"]] if e["category"] == "ANC" and e["status"] == "completed"
                      and e["facility_id"] == fac], key=lambda e: e["date"])
        for j in range(1, 6):
            e = anc[j - 1] if j <= len(anc) else None
            o = obs_by_enc.get(e["enc_id"], {}) if e else {}
            row[f"ANC{j} Date"] = regdate(e["date"]) if e else None
            row[f"ANC{j} Wt (kg)"] = o.get("weight")
            row[f"ANC{j} BP"] = f"{o['bp_systolic']}/{o['bp_diastolic']}" if "bp_systolic" in o else None
            row[f"ANC{j} Hb"] = o.get("hemoglobin")
        appts = sorted(appts_by_key[pr["key"]], key=lambda a: a["due"])
        row["Next Due Date"] = regdate(appts[-1]["due"]) if appts else None
        row["Delivery Date"] = regdate(pr["delivery_date"]) if pr["delivery_date"] else None
        row["Place of Delivery"] = (FAC[pr["delivery_facility"]]["name"] if pr["delivery_facility"] else None)
        row["Type of Delivery"] = pr["delivery_mode"]
        child = next((ch for ch in c.children if ch["episode_id"] == pr["episode_id"]), None)
        row["Baby Sex"] = child["sex"] if child else None
        row["Birth Wt (gm)"] = child["birth_weight_g"] if child else None
        pnc = sorted([e for e in encs_by_key[pr["key"]] if e["category"] == "PNC" and e["facility_id"] == fac],
                     key=lambda e: e["date"])
        for j in range(1, 4):
            row[f"PNC{j} Date"] = regdate(pnc[j - 1]["date"]) if j <= len(pnc) else None
        remarks = []
        if pr["delivery_facility"] and pr["delivery_facility"] != fac:
            remarks.append(f"Referred to {FAC[pr['delivery_facility']]['name']} for delivery")
        if rng.random() < .12:
            remarks.append("Called on phone - not reachable")
        if rng.random() < .1:
            remarks.append("MCP card issued")
        row["Remarks"] = "; ".join(remarks) or None
        rows.append(row)

        for e in anc:
            if labs_by_enc.get(e["enc_id"]):
                n_pdf += 1
                _lab_pdf(out / "lab_reports" / f"LAB-{fac}-{e['enc_id']}.pdf", FAC[fac]["name"], p, e,
                         labs_by_enc[e["enc_id"]])
    df = pd.DataFrame(rows)
    with pd.ExcelWriter(out / f"ANC_Register_{FAC[fac]['name'].replace(' ', '_')}.xlsx") as xw:
        df.to_excel(xw, sheet_name="ANC Register", index=False)
    return {"facility": fac, "register_rows": len(rows), "lab_pdfs": n_pdf}


def _lab_pdf(path: Path, facility: str, p: dict, enc: dict, labs: list[dict]) -> None:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    cv = canvas.Canvas(str(path), pagesize=A4)
    w, h = A4
    y = h - 60
    cv.setFont("Helvetica-Bold", 14)
    cv.drawString(50, y, f"{facility.upper()} - LABORATORY / IMAGING REPORT")
    y -= 18
    cv.setFont("Helvetica", 9)
    cv.drawString(50, y, "SYNTHETIC DEMO DOCUMENT - NOT A REAL PATIENT")
    y -= 26
    cv.setFont("Helvetica", 11)
    for line in [f"Lab No: {path.stem}", f"Patient Name: {p['name']}", f"RCH ID: {p['rch_id']}",
                 f"Age: {p['age']} Y   Sex: F", f"Sample Date: {enc['date'].strftime('%d/%m/%Y')}"]:
        cv.drawString(50, y, line)
        y -= 16
    y -= 10
    cv.setFont("Helvetica-Bold", 11)
    cv.drawString(50, y, "Test | Result | Reported on")
    y -= 18
    cv.setFont("Helvetica", 10)
    for lab in labs:
        res = lab["result"] or "Result awaited"
        rep = lab["resulted_on"].strftime("%d/%m/%Y") if lab["resulted_on"] else "-"
        cv.drawString(50, y, f"{lab['local_name']} | {res} | {rep}"[:110])
        y -= 16
    cv.drawString(50, 60, "Verified by: Lab Technician (synthetic)")
    cv.save()


def write_all(c: Cohort, raw_dir: Path, seed: int = 7) -> dict:
    rng = random.Random(seed)
    manifest = {"reference_date": c.reference_date.isoformat(), "sources": []}
    for f in FACILITIES:
        fac = f["facility_id"]
        if f["source_system"] == "ehr_export":
            info = _write_ehr(c, fac, raw_dir / f"ehr_{fac}", rng)
            manifest["sources"].append({**info, "type": "ehr_export", "path": f"ehr_{fac}"})
        else:
            info = _write_register(c, fac, raw_dir / f"register_{fac}", rng)
            manifest["sources"].append({**info, "type": "excel_register", "path": f"register_{fac}"})
    # reference data the clinic would have anyway (facility master, staff list)
    pd.DataFrame([{k: v for k, v in f.items() if k not in ("lang_mix", "villages")} for f in FACILITIES]).to_csv(
        raw_dir / "facilities.csv", index=False)
    pd.DataFrame(PROVIDERS).to_csv(raw_dir / "providers.csv", index=False)
    manifest["ground_truth"] = {
        "patients": len(c.patients), "pregnancies": len(c.pregnancies), "encounters": len(c.encounters),
        "completed_encounters": sum(e["status"] == "completed" for e in c.encounters),
        "children": len(c.children), "labs": len(c.labs), "notes": len(c.notes),
    }
    (raw_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))
    return manifest


__all__ = ["write_all", "TESTS"]
