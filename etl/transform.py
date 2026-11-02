"""CLEAN -> NORMALIZE -> LINK: staging frames to the canonical unified data layer.

Every step records counts in `report` and failing rows in the quarantine, so
the data-quality report can show exactly what happened to each source.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta

import pandas as pd
from rapidfuzz import fuzz

from etl import vocab as V
from etl.clean import Quarantine, blank, dedupe, name_key, normalize_name, normalize_phone, parse_date, to_float
from etl.extract import Staging


def _month(d: date | None) -> str | None:
    return d.strftime("%Y-%m") if d else None


def _nearest(value: int, options: list[tuple]) -> tuple:
    return min(options, key=lambda o: abs(o[0] - value))


class Transformer:
    def __init__(self, st: Staging, reference_date: date):
        self.st = st
        self.ref = reference_date
        self.q = Quarantine()
        self.report: dict = {"steps": {}}
        self.pid_map: dict[tuple[str, str], str] = {}     # (source_system, source_patient_id) -> CS id
        self.rch_map: dict[str, str] = {}
        self.preg_map: dict[tuple[str, str], str] = {}
        self.child_map: dict[tuple[str, str], str] = {}
        self.visit_map: dict[tuple[str, str], str] = {}
        self.out: dict[str, pd.DataFrame] = {}

    # ------------------------------------------------------------------ patients + MPI
    def patients(self) -> None:
        df = self.st.get("patients")
        rows = []
        for r in df.to_dict("records"):
            name = normalize_name(r["name"])
            if not name:
                self.q.add(r["source_system"], "patients", "missing name", r)
                continue
            rows.append({**r, "name": name, "phone": normalize_phone(r["phone"]),
                         "caregiver_phone": normalize_phone(r["caregiver_phone"]),
                         "rch_id": "" if blank(r["rch_id"]) else str(r["rch_id"]).split(".")[0],
                         "registered_on": parse_date(r["registered_on"]),
                         "language": V.LANGUAGE.get(V.key(r["language"]), "en"),
                         "age": int(to_float(r["age"]) or 0) or None})
        rows.sort(key=lambda r: (r["registered_on"] is None, r["registered_on"] or date.max))

        clusters: list[list[dict]] = []
        by_rch: dict[str, int] = {}
        by_phone: dict[str, list[tuple[str, int]]] = defaultdict(list)
        linked = {"by_rch_id": 0, "by_name_phone": 0}
        for r in rows:
            cid = None
            if r["rch_id"] and r["rch_id"] in by_rch:
                cid = by_rch[r["rch_id"]]
                linked["by_rch_id"] += 1
            elif r["phone"]:
                for nk, c in by_phone[r["phone"]]:
                    if fuzz.ratio(nk, name_key(r["name"])) >= 90:
                        cid = c
                        linked["by_name_phone"] += 1
                        break
            if cid is None:
                cid = len(clusters)
                clusters.append([])
            clusters[cid].append(r)
            if r["rch_id"]:
                by_rch.setdefault(r["rch_id"], cid)
            if r["phone"]:
                by_phone[r["phone"]].append((name_key(r["name"]), cid))

        patients, idents = [], []
        for i, recs in enumerate(clusters, 1):
            pid = f"CS-{i:06d}"
            master = next((x for x in recs if x["registered_on"]), recs[0])
            for x in recs:
                self.pid_map[(x["source_system"], x["source_id"])] = pid
                idents.append({"patient_id": pid, "source_system": x["source_system"], "source_id": x["source_id"]})
                if x["rch_id"]:
                    self.rch_map[x["rch_id"]] = pid

            def first(field):
                return next((x[field] for x in [master, *recs] if not blank(x[field])), None)

            patients.append({
                "patient_id": pid, "rch_id": first("rch_id"), "full_name": master["name"], "age_years": first("age"),
                "phone": first("phone"), "email": first("email"), "preferred_language": master["language"],
                "village": first("village"), "district": first("district"), "facility_id": master["facility_id"],
                "caregiver_name": first("caregiver_name"), "caregiver_relation": first("caregiver_relation"),
                "caregiver_phone": first("caregiver_phone"),
                "consent_sms": str(master["consent_sms"]).upper().startswith("Y"),
                "consent_whatsapp": str(master["consent_whatsapp"]).upper().startswith("Y"),
                "consent_email": str(master["consent_email"]).upper().startswith("Y"),
                "registered_on": master["registered_on"], "source_system": master["source_system"]})
        self.out["patients"] = pd.DataFrame(patients)
        self.out["patient_identifiers"] = pd.DataFrame(idents)
        self.report["steps"]["patient_linkage"] = {
            "source_records": len(rows), "canonical_patients": len(patients),
            "records_merged": len(rows) - len(patients), **linked,
            "patients_in_multiple_sources": sum(len({x["source_system"] for x in c}) > 1 for c in clusters)}

    def _pid(self, source_system: str, source_patient_id: str) -> str | None:
        if str(source_patient_id).startswith("rch:"):
            return self.rch_map.get(source_patient_id[4:])
        return self.pid_map.get((source_system, source_patient_id))

    # ------------------------------------------------------------------ pregnancies
    def pregnancies(self) -> None:
        df = self.st.get("pregnancies")
        by_patient: dict[str, list[dict]] = defaultdict(list)
        for r in df.to_dict("records"):
            pid = self._pid(r["source_system"], r["source_patient_id"])
            if not pid:
                self.q.add(r["source_system"], "pregnancies", "unlinked patient", r)
                continue
            lmp, edd = parse_date(r["lmp"]), parse_date(r["edd"])
            lmp = lmp or (edd - timedelta(days=280) if edd else None)
            if not lmp:
                self.q.add(r["source_system"], "pregnancies", "missing LMP and EDD", r)
                continue
            by_patient[pid].append({**r, "lmp": lmp, "edd": edd or lmp + timedelta(days=280),
                                    "registered_on": parse_date(r["registered_on"]),
                                    "delivery_date": parse_date(r["delivery_date"])})
        rows = []
        merged = 0
        for pid, recs in by_patient.items():
            recs.sort(key=lambda x: (x["registered_on"] is None, x["lmp"]))
            episodes: list[list[dict]] = []
            for r in recs:
                ep = next((e for e in episodes if abs((e[0]["lmp"] - r["lmp"]).days) <= 21), None)
                if ep is None:
                    episodes.append([r])
                else:
                    ep.append(r)
                    merged += 1
            for k, ep in enumerate(episodes, 1):
                prid = f"PR-{pid[3:]}-{k}"
                for r in ep:
                    self.preg_map[(r["source_system"], r["source_episode_id"])] = prid
                master = ep[0]
                deliv = next((r for r in ep if r["delivery_date"] and not blank(r["delivery_mode"])), None) or \
                    next((r for r in ep if r["delivery_date"]), None)
                reg = min((r["registered_on"] for r in ep if r["registered_on"]), default=None)
                rows.append({
                    "pregnancy_id": prid, "patient_id": pid, "lmp": master["lmp"], "edd": master["edd"],
                    "gravida": int(to_float(master["gravida"]) or 0) or None,
                    "parity": int(to_float(master["parity"])) if to_float(master["parity"]) is not None else None,
                    "registration_date": reg,
                    "registration_ga_weeks": round((reg - master["lmp"]).days / 7, 1) if reg else None,
                    "registration_month": _month(reg),
                    "delivery_date": deliv["delivery_date"] if deliv else None,
                    "delivery_mode": None if not deliv or blank(deliv["delivery_mode"]) else deliv["delivery_mode"],
                    "delivery_facility_id": (deliv["delivery_facility_id"] or None) if deliv else None,
                    "status": "antenatal", "anc_visits_completed": 0})
        self.out["pregnancies"] = pd.DataFrame(rows)
        self.report["steps"]["pregnancies"] = {"source_episodes": len(df), "canonical_pregnancies": len(rows),
                                               "episodes_merged_across_sources": merged}

    # ------------------------------------------------------------------ children
    def children(self) -> None:
        df = self.st.get("children")
        preg = self.out["pregnancies"].set_index("pregnancy_id")
        rows = []
        for r in df.to_dict("records"):
            mother = self._pid(r["source_system"], r["source_mother_id"])
            prid = self.preg_map.get((r["source_system"], r["source_episode_id"]))
            if not mother and prid:
                mother = preg.loc[prid, "patient_id"]
            dob = parse_date(r["dob"])
            if not mother or not dob:
                self.q.add(r["source_system"], "children", "unlinked mother or missing DOB", r)
                continue
            dup = next((c for c in rows if c["mother_patient_id"] == mother and abs((c["dob"] - dob).days) <= 2), None)
            if dup:
                self.child_map[(r["source_system"], r["source_child_id"])] = dup["child_id"]
                continue
            cid = f"CH-{len(rows) + 1:05d}"
            self.child_map[(r["source_system"], r["source_child_id"])] = cid
            bw = to_float(r["birth_weight_g"])
            rows.append({"child_id": cid, "mother_patient_id": mother, "pregnancy_id": prid,
                         "full_name": normalize_name(r["name"]), "sex": r["sex"] or None, "dob": dob,
                         "birth_weight_g": int(bw) if bw else None, "facility_id": r["facility_id"]})
        self.out["children"] = pd.DataFrame(rows)

    # ------------------------------------------------------------------ visits
    def visits(self) -> None:
        df, n_dup = dedupe(self.st.get("encounters"), ["source_system", "source_encounter_id"])
        preg = self.out["pregnancies"]
        preg_by_patient = defaultdict(list)
        for p in preg.to_dict("records"):
            preg_by_patient[p["patient_id"]].append(p)
        preg_idx = {p["pregnancy_id"]: p for p in preg.to_dict("records")}
        child_dob = {c["child_id"]: c["dob"] for c in self.out["children"].to_dict("records")}
        rows = []
        for r in df.to_dict("records"):
            d = parse_date(r["date"])
            pid = self._pid(r["source_system"], r["source_patient_id"])
            cat = V.ENCOUNTER_TYPE.get(V.key(r["type_raw"]))
            status = V.ENCOUNTER_STATUS.get(V.key(r["status_raw"]))
            reason = (not d and "unparseable date") or (d and d > self.ref and "date in the future") or \
                     (not pid and "unlinked patient") or (not cat and f"unmapped encounter type '{r['type_raw']}'") or \
                     (not status and f"unmapped status '{r['status_raw']}'")
            if reason:
                self.q.add(r["source_system"], "encounters", reason, r)
                continue
            prid = self.preg_map.get((r["source_system"], r["source_episode_id"]))
            if not prid:  # fall back to date window
                prid = next((p["pregnancy_id"] for p in preg_by_patient[pid]
                             if p["lmp"] <= d <= (p["delivery_date"] or p["edd"]) + timedelta(days=120)), None)
            sid = r["source_encounter_id"]
            vid = f"V-{sid}" if sid.startswith(r["facility_id"]) else f"V-{r['facility_id']}-{sid}"
            self.visit_map[(r["source_system"], sid)] = vid
            rows.append({"visit_id": vid, "patient_id": pid,
                         "child_id": self.child_map.get((r["source_system"], r["source_child_id"])) or None,
                         "pregnancy_id": prid, "facility_id": r["facility_id"], "provider_id": r["provider_id"] or None,
                         "visit_date": d, "visit_month": _month(d), "visit_category": cat, "visit_type": cat,
                         "sequence": None, "ga_weeks": None, "status": status, "source_system": r["source_system"]})
        vis = pd.DataFrame(rows)

        # derive labels: ANC sequence, PNC day, immunization session, gestational age
        vis = vis.sort_values(["pregnancy_id", "visit_date"]).reset_index(drop=True)
        anc_count: dict[str, int] = defaultdict(int)
        for i, v in vis.iterrows():
            p = preg_idx.get(v["pregnancy_id"])
            if v["visit_category"] in ("ANC", "Delivery") and p:
                vis.at[i, "ga_weeks"] = round((v["visit_date"] - p["lmp"]).days / 7, 1)
            if v["visit_category"] == "ANC":
                n = anc_count[v["pregnancy_id"]] + 1
                if v["status"] == "completed":
                    anc_count[v["pregnancy_id"]] = n
                vis.at[i, "sequence"] = n
                vis.at[i, "visit_type"] = f"ANC{min(n, 5)}"
            elif v["visit_category"] == "Delivery":
                vis.at[i, "visit_type"] = "Delivery"
            elif v["visit_category"] == "PNC" and p and p["delivery_date"]:
                vis.at[i, "visit_type"] = _nearest((v["visit_date"] - p["delivery_date"]).days, V.PNC_LABELS)[1]
            elif v["visit_category"] == "Child" and v["child_id"] in child_dob:
                vis.at[i, "visit_type"] = _nearest((v["visit_date"] - child_dob[v["child_id"]]).days,
                                                   V.IMMUNIZATION_SESSIONS)[1]
        self.out["visits"] = vis
        self.report["steps"]["visits"] = {"source_rows": len(df) + n_dup, "duplicates_removed": n_dup,
                                          "loaded": len(vis)}

    # ------------------------------------------------------------------ observations
    def observations(self) -> None:
        df, n_dup = dedupe(self.st.get("observations"))
        vis = self.out["visits"].set_index("visit_id")
        rows, unmapped = [], defaultdict(int)

        def add(r, vid, code, value_num=None, value_text=None, unit=None):
            display, std_unit, loinc = V.obs_display(code)
            lo_hi = V.PLAUSIBLE.get(code)
            if value_num is not None and lo_hi and not (lo_hi[0] <= value_num <= lo_hi[1]):
                self.q.add(r["source_system"], "observations", f"implausible {code} value (data-entry check)", r)
                return
            v = vis.loc[vid]
            rows.append({"visit_id": vid, "patient_id": v["patient_id"], "child_id": v["child_id"], "code": code,
                         "display": display, "loinc": loinc, "value_num": value_num, "value_text": value_text,
                         "unit": unit or std_unit, "observed_on": parse_date(r["date"]) or v["visit_date"]})

        for r in df.to_dict("records"):
            vid = self.visit_map.get((r["source_system"], r["source_encounter_id"]))
            if not vid:
                self.q.add(r["source_system"], "observations", "unlinked encounter", r)
                continue
            code = V.OBS_SYNONYMS.get(V.key(r["name_raw"]))
            raw, unit = str(r["value_raw"]).strip(), str(r["unit_raw"] or "").strip().lower()
            if not code:
                unmapped[r["name_raw"]] += 1
                self.q.add(r["source_system"], "observations", "unmapped observation name", r)
                continue
            if code == "bp_combined":
                parts = raw.split("/")
                if len(parts) != 2 or to_float(parts[0]) is None or to_float(parts[1]) is None:
                    self.q.add(r["source_system"], "observations", "unparseable BP", r)
                    continue
                add(r, vid, "bp_systolic", to_float(parts[0]))
                add(r, vid, "bp_diastolic", to_float(parts[1]))
            elif code == "urine_albumin":
                add(r, vid, code, value_text=raw.title())
            else:
                val = to_float(raw)
                if val is None:
                    self.q.add(r["source_system"], "observations", "non-numeric value", r)
                    continue
                if code == "infant_weight" and (unit == "g" or val > 100):
                    val = round(val / 1000, 3)       # grams -> kg
                # g%, g/dl, g/dL are equivalent units for haemoglobin -> g/dL
                add(r, vid, code, value_num=val)
        self.out["observations"] = pd.DataFrame(rows)
        self.report["steps"]["observations"] = {"source_rows": len(df) + n_dup, "duplicates_removed": n_dup,
                                                "loaded": len(rows), "unmapped_names": dict(unmapped)}

    # ------------------------------------------------------------------ investigations
    def investigations(self) -> None:
        df, n_dup = dedupe(self.st.get("labs"), ["source_system", "source_order_id"])
        vis = self.out["visits"]
        anc_by_patient_date = {(v["patient_id"], v["visit_date"]): v["visit_id"]
                               for v in vis.to_dict("records") if v["status"] == "completed"}
        vis_facility = dict(zip(vis["visit_id"], vis["facility_id"]))
        rows, unmapped = [], defaultdict(int)
        for i, r in enumerate(df.to_dict("records"), 1):
            pid = self._pid(r["source_system"], r["source_patient_id"])
            code = V.TEST_SYNONYMS.get(V.key(r["test_raw"]))
            ordered = parse_date(r["ordered_on"])
            if not code:
                unmapped[r["test_raw"]] += 1
            reason = (not pid and "unlinked patient") or (not code and "unmapped test name") or \
                     (not ordered and "missing order date")
            if reason:
                self.q.add(r["source_system"], "investigations", reason, r)
                continue
            vid = self.visit_map.get((r["source_system"], r["source_encounter_id"])) or \
                anc_by_patient_date.get((pid, ordered))
            resulted = parse_date(r["resulted_on"])
            display, cat = V.test_display(code)
            rows.append({"investigation_id": f"INV-{i:06d}", "visit_id": vid, "patient_id": pid, "test_code": code,
                         "test_name": display, "category": cat, "ordered_on": ordered, "ordered_month": _month(ordered),
                         "resulted_on": resulted, "status": "resulted" if resulted else "pending",
                         "turnaround_days": (resulted - ordered).days if resulted else None,
                         "result_summary": None if blank(r["result"]) else str(r["result"])[:200],
                         "report_doc_id": f"DOC-{r['report_doc_id'][4:]}" if r["report_doc_id"] else None,
                         "source_system": r["source_system"], "_facility": vis_facility.get(vid)})
        self.out["investigations"] = pd.DataFrame(rows)
        self.report["steps"]["investigations"] = {"source_rows": len(df) + n_dup, "duplicates_removed": n_dup,
                                                  "loaded": len(rows), "unmapped_tests": dict(unmapped)}

    # ------------------------------------------------------------------ immunizations
    def immunizations(self) -> None:
        df = self.st.get("immunizations")
        vis = self.out["visits"]
        child_visits = {(v["child_id"], v["visit_type"]): v["visit_id"] for v in vis.to_dict("records") if v["child_id"]}
        rows = []
        for i, r in enumerate(df.to_dict("records"), 1):
            cid = self.child_map.get((r["source_system"], r["source_child_id"]))
            due = parse_date(r["due"])
            if not cid or not due:
                self.q.add(r["source_system"], "immunizations", "unlinked child or missing due date", r)
                continue
            given = parse_date(r["given"])
            session = V.SESSION_BY_LABEL.get(r["schedule"], "Immunization")
            rows.append({"imm_id": f"IMM-{i:06d}", "child_id": cid, "vaccine": r["vaccine"],
                         "schedule_label": r["schedule"], "due_on": due, "given_on": given,
                         "status": "given" if given else ("overdue" if due < self.ref else "due"),
                         "visit_id": child_visits.get((cid, session)) if given else None})
        self.out["immunizations"] = pd.DataFrame(rows)

    # ------------------------------------------------------------------ documents
    def documents(self) -> None:
        df = self.st.get("documents")
        child_mother = dict(zip(self.out["children"]["child_id"], self.out["children"]["mother_patient_id"]))
        rows = []
        for r in df.to_dict("records"):
            pid = self._pid(r["source_system"], r["source_patient_id"])
            cid = self.child_map.get((r["source_system"], r["source_child_id"])) if r["source_child_id"] else None
            pid = pid or child_mother.get(cid)
            d = parse_date(r["doc_date"])
            if not pid or not d:
                self.q.add(r["source_system"], "documents", "unlinked patient or missing date", r)
                continue
            sid = str(r["source_doc_id"])
            rows.append({"doc_id": sid if sid.startswith("DOC-") else f"DOC-{sid}", "patient_id": pid, "child_id": cid,
                         "visit_id": self.visit_map.get((r["source_system"], r["source_encounter_id"])),
                         "doc_type": r["doc_type"], "title": r["title"], "doc_date": d, "author": r["author"],
                         "text": r["text"], "source_system": r["source_system"], "source_file": r["source_file"]})
        self.out["documents"] = pd.DataFrame(rows)
        # back-fill visit links for PDF reports via the investigations parsed from them
        inv = self.out["investigations"]
        doc_visit = inv.dropna(subset=["report_doc_id", "visit_id"]).drop_duplicates("report_doc_id") \
            .set_index("report_doc_id")["visit_id"].to_dict()
        docs = self.out["documents"]
        docs["visit_id"] = [v if v else doc_visit.get(d) for d, v in zip(docs["doc_id"], docs["visit_id"])]

    # ------------------------------------------------------------------ pregnancy status
    def pregnancy_status(self) -> None:
        preg, vis = self.out["pregnancies"], self.out["visits"]
        completed = vis[vis["status"] == "completed"]
        anc = completed[completed["visit_category"] == "ANC"].groupby("pregnancy_id").size().to_dict()
        last_contact = completed.groupby("pregnancy_id")["visit_date"].max().to_dict()
        statuses = []
        for p in preg.to_dict("records"):
            last = last_contact.get(p["pregnancy_id"])
            if p["delivery_date"]:
                s = "postnatal_closed" if p["delivery_date"] + timedelta(days=42) < self.ref else "delivered"
            elif p["edd"] + timedelta(days=28) < self.ref or (last and (self.ref - last).days > 70):
                s = "no_recent_contact"
            else:
                s = "antenatal"
            statuses.append(s)
        preg["status"] = statuses
        preg["anc_visits_completed"] = [anc.get(x, 0) for x in preg["pregnancy_id"]]

    def run(self) -> dict[str, pd.DataFrame]:
        self.patients()
        self.pregnancies()
        self.children()
        self.visits()
        self.observations()
        self.investigations()
        self.immunizations()
        self.documents()
        self.pregnancy_status()
        return self.out
