"""Simulate a synthetic MCH cohort ("ground truth") for three facilities.

The simulation produces events in time: registration, scheduled ANC contacts
with realistic attendance / no-shows / drop-out, investigations with turnaround
and pending results, deliveries (with inter-facility referral), PNC contacts and
child immunizations. Writers in `writers.py` then serialise this ground truth
into the *messy* formats clinics actually keep (EHR CSV exports, an Excel
register, PDF lab reports, free-text notes).

No real patient data is used. Parameters are illustrative, not epidemiological
estimates.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import date, timedelta

from data_generator import notes as N
from data_generator.reference import (
    ANC_EXTRA_WEEK, ANC_TARGET_WEEKS, CAREGIVER_RELATIONS, COMPLAINTS, DOCTOR_BY_FACILITY, ELDER_NAMES,
    FACILITIES, FACILITY_WEIGHTS, FIRST_NAMES, MALE_NAMES, PAEDIATRICIAN_BY_FACILITY, PNC_DAYS, PROVIDERS,
    SURNAMES, TESTS, UIP_SCHEDULE,
)

FAC = {f["facility_id"]: f for f in FACILITIES}
PROV = {p["provider_id"]: p for p in PROVIDERS}


@dataclass
class Cohort:
    reference_date: date
    patients: list[dict] = field(default_factory=list)
    pregnancies: list[dict] = field(default_factory=list)
    encounters: list[dict] = field(default_factory=list)
    observations: list[dict] = field(default_factory=list)
    labs: list[dict] = field(default_factory=list)
    appointments: list[dict] = field(default_factory=list)
    children: list[dict] = field(default_factory=list)
    immunizations: list[dict] = field(default_factory=list)
    notes: list[dict] = field(default_factory=list)


def _weighted(rng: random.Random, mapping: dict):
    keys, weights = zip(*mapping.items())
    return rng.choices(keys, weights=weights, k=1)[0]


def _clip(x, lo, hi):
    return max(lo, min(hi, x))


class _Sim:
    def __init__(self, seed: int, ref: date):
        self.rng = random.Random(seed)
        self.ref = ref
        self.c = Cohort(reference_date=ref)
        self._n = {"enc": 0, "lab": 0, "appt": 0, "note": 0, "child": 0}

    def _id(self, kind: str, prefix: str) -> str:
        self._n[kind] += 1
        return f"{prefix}{self._n[kind]:06d}"

    # ------------------------------------------------------------------ people
    def _make_patient(self, idx: int) -> dict:
        r = self.rng
        fac = _weighted(r, FACILITY_WEIGHTS)
        lang = _weighted(r, FAC[fac]["lang_mix"])
        first, last = r.choice(FIRST_NAMES[lang]), r.choice(SURNAMES[lang])
        relation = _weighted(r, dict(CAREGIVER_RELATIONS))
        if relation == "Husband":
            cg_name = f"{r.choice(MALE_NAMES[lang])} {last}"
        else:
            cg_name = r.choice(ELDER_NAMES[lang])
        has_email = r.random() < .18
        return {
            "key": f"K{idx:05d}",
            "rch_id": "1" + "".join(str(r.randint(0, 9)) for _ in range(11)),
            "first": first,
            "name": f"{first} {last}",
            "age": int(_clip(round(r.gauss(25, 4)), 18, 40)),
            "phone": "+9190000" + f"{r.randint(0, 99999):05d}",
            "email": f"{first.lower()}.{last.lower().replace(chr(39), '')}{idx}@example.com" if has_email else None,
            "language": lang,
            "village": r.choice(FAC[fac]["villages"]),
            "district": FAC[fac]["district"],
            "facility_id": fac,
            "caregiver_name": cg_name,
            "caregiver_relation": relation,
            "caregiver_phone": "+9190001" + f"{r.randint(0, 99999):05d}",
            "consent_sms": r.random() < .93,
            "consent_whatsapp": r.random() < .62,
            "consent_email": has_email and r.random() < .8,
        }

    # ------------------------------------------------------------------ events
    def _encounter(self, p: dict, preg: dict | None, fac: str, d: date, category: str, vtype: str,
                   status: str = "completed", child: dict | None = None, ga: float | None = None,
                   provider: str | None = None) -> dict:
        enc = {
            "enc_id": self._id("enc", "E"), "key": p["key"], "episode_id": preg["episode_id"] if preg else None,
            "child_key": child["child_key"] if child else None, "facility_id": fac, "date": d,
            "category": category, "vtype": vtype, "status": status, "ga": ga,
            "provider_id": provider or DOCTOR_BY_FACILITY[fac],
        }
        self.c.encounters.append(enc)
        return enc

    def _appointment(self, p: dict, src: dict, purpose: str, label: str, due: date, child: dict | None = None):
        self.c.appointments.append({
            "appt_id": self._id("appt", "A"), "key": p["key"], "child_key": child["child_key"] if child else None,
            "src_enc": src["enc_id"], "purpose": purpose, "label": label, "due": due,
            "facility_id": src["facility_id"],
        })

    def _obs(self, enc: dict, code: str, value, d: date | None = None):
        self.c.observations.append({"enc_id": enc["enc_id"], "key": enc["key"], "child_key": enc["child_key"],
                                    "code": code, "value": value, "date": d or enc["date"]})

    def _order_tests(self, enc: dict, codes: list[str], pt_state: dict) -> list[str]:
        r = self.rng
        local_names = []
        for code in codes:
            display, cat, variants = TESTS[code]
            tat = (min(r.expovariate(1 / 1.2), 6) if cat == "lab" else r.randint(1, 10))
            resulted = enc["date"] + timedelta(days=int(round(tat)))
            never = r.random() < (.08 if cat == "lab" else .15)
            if never or resulted > self.ref:
                resulted = None
            result = self._result_text(code, enc, pt_state) if resulted else None
            self.c.labs.append({
                "order_id": self._id("lab", "L"), "enc_id": enc["enc_id"], "key": enc["key"],
                "test_code": code, "local_name": r.choice(variants), "ordered_on": enc["date"],
                "resulted_on": resulted, "result": result, "facility_id": enc["facility_id"],
            })
            if code == "cbc" and resulted:
                self._obs(enc, "hemoglobin", round(_clip(pt_state["hb"] + r.gauss(0, .4), 6.5, 14.5), 1), resulted)
            local_names.append(display)
        return local_names

    def _result_text(self, code: str, enc: dict, s: dict) -> str:
        r = self.rng
        ga = enc["ga"] or 0
        return {
            "cbc": f"Hb {_clip(s['hb'] + r.gauss(0, .3), 6.5, 14.5):.1f} g/dL; TLC and platelets reported",
            "blood_group": s["blood_group"],
            "hiv": "Non-reactive",
            "vdrl": "Non-reactive",
            "hbsag": "Negative",
            "urine_routine": "Albumin: Nil; Sugar: Nil",
            "ogtt": f"2-hour plasma glucose {int(_clip(r.gauss(112, 16), 70, 190))} mg/dL",
            "tsh": f"TSH {_clip(r.gauss(2.1, .8), .3, 6.5):.2f} mIU/L",
            "usg_dating": f"Single live intrauterine gestation; CRL corresponds to {int(ga)}w{r.randint(0, 6)}d",
            "usg_anomaly": "Single live intrauterine fetus; detailed anomaly survey reported by radiologist",
            "usg_growth": "Single live fetus; biometry and liquor reported by radiologist",
        }[code]

    # ------------------------------------------------------------------ pregnancy journey
    def simulate_mother(self, idx: int) -> None:
        r, ref = self.rng, self.ref
        p = self._make_patient(idx)
        # LMP 70-560 days before reference date; registration GA mixture (most in 1st trimester)
        for _ in range(20):
            lmp = ref - timedelta(days=r.randint(70, 560))
            u = r.random()
            reg_ga = r.uniform(6, 12.5) if u < .6 else (r.uniform(13, 20) if u < .9 else r.uniform(21, 28))
            max_ga = (ref - lmp).days / 7 - .3
            reg_ga = min(reg_ga, max_ga)
            if reg_ga >= 6:
                break
        reg_date = lmp + timedelta(days=round(reg_ga * 7))
        gravida = r.choices([1, 2, 3, 4], weights=[.42, .35, .16, .07])[0]
        parity = max(0, gravida - 1 - (1 if gravida > 1 and r.random() < .1 else 0))
        delivery_ga = _clip(r.gauss(39, 1.2), 34, 41.5)
        preg = {
            "episode_id": f"EP{idx:05d}", "key": p["key"], "lmp": lmp, "edd": lmp + timedelta(days=280),
            "gravida": gravida, "parity": parity, "reg_date": reg_date, "delivery_date": None,
            "delivery_mode": None, "delivery_facility": None, "delivery_ga": delivery_ga,
        }
        p["registered_on"] = reg_date
        self.c.patients.append(p)
        self.c.pregnancies.append(preg)

        fac = p["facility_id"]
        p_attend = r.betavariate(8, 2)
        hazard = .06
        state = {"hb": _clip(r.gauss(10.9, 1.2), 7, 14), "blood_group": r.choice(
            ["A Positive", "B Positive", "O Positive", "AB Positive", "B Positive", "O Positive", "O Negative"]),
            "w0": _clip(r.gauss(52, 8), 38, 88), "sys0": r.gauss(110, 8), "dia0": r.gauss(70, 6),
            "tests_done": set(), "cbc_count": 0}
        delivery_date = lmp + timedelta(days=round(delivery_ga * 7))

        anc_seq = 0
        prev = None
        dropped = False

        def complete_anc(d: date) -> dict:
            nonlocal anc_seq
            anc_seq += 1
            ga = (d - lmp).days / 7
            enc = self._encounter(p, preg, fac, d, "ANC", f"ANC{min(anc_seq, 5)}", ga=ga)
            o = {"weight": round(state["w0"] + max(0, ga - 13) * .42 + r.gauss(0, .5), 1),
                 "bp_systolic": round(state["sys0"] + r.gauss(0, 5)), "bp_diastolic": round(state["dia0"] + r.gauss(0, 4)),
                 "urine_albumin": "Nil" if r.random() < .93 else "Trace"}
            if ga >= 20:
                o["fundal_height"] = round(ga + r.gauss(0, 1.5))
                o["fetal_heart_rate"] = round(r.gauss(142, 8))
            for k, v in o.items():
                self._obs(enc, k, v)
            codes = []
            if anc_seq == 1:
                codes = ["cbc", "blood_group", "hiv", "vdrl", "hbsag", "urine_routine"]
                if r.random() < .4:
                    codes.append("tsh")
                if ga <= 13.5:
                    codes.append("usg_dating")
            if 18 <= ga < 23 and "usg_anomaly" not in state["tests_done"] and r.random() < .85:
                codes.append("usg_anomaly")
            if 24 <= ga < 29 and "ogtt" not in state["tests_done"] and r.random() < .9:
                codes.append("ogtt")
            if ga >= 30 and state["cbc_count"] < 2 and "cbc" not in codes:
                codes.append("cbc")
            if ga >= 34 and "usg_growth" not in state["tests_done"] and r.random() < .3:
                codes.append("usg_growth")
            state["tests_done"].update(codes)
            state["cbc_count"] += codes.count("cbc")
            enc["_tests"] = self._order_tests(enc, codes, state) if codes else []
            enc["_obs"] = o
            return enc

        def add_anc_note(enc: dict | None, next_due: date | None, next_label: str | None):
            if enc is None or FAC[fac]["source_system"] != "ehr_export":
                return
            text = N.anc_note(r, facility=FAC[fac]["name"], provider=PROV[enc["provider_id"]]["name"], patient=p,
                              preg=preg, visit=enc, obs=enc["_obs"], tests=enc["_tests"], next_due=next_due,
                              next_label=next_label, complaint=r.choice(COMPLAINTS))
            self._note(enc, "clinical_note", f"{enc['vtype']} visit note", text)

        # ---- ANC1 (registration)
        prev = complete_anc(reg_date)
        targets = [w for w in ANC_TARGET_WEEKS if w >= reg_ga + 4]
        if r.random() < .35:
            targets.append(ANC_EXTRA_WEEK)
        pending_note_for = prev
        for target_w in targets:
            due = lmp + timedelta(days=target_w * 7)
            if due >= delivery_date:
                break
            label = f"ANC{min(anc_seq + 1, 5)}"
            self._appointment(p, prev, "ANC visit", label, due)
            add_anc_note(pending_note_for, due, label)
            pending_note_for = None
            if prev["_tests"] and not prev.get("_review_booked") and r.random() < .5:
                prev["_review_booked"] = True
                self._appointment(p, prev, "Report review", "Investigation report review", prev["date"] + timedelta(days=14))
            if due > ref:
                break
            if r.random() < hazard:
                dropped = True
                break
            if r.random() < p_attend:
                d = min(due + timedelta(days=r.randint(-3, 6)), ref)
                prev = complete_anc(d)
                pending_note_for = prev
            else:
                if FAC[fac]["source_system"] == "ehr_export":
                    self._encounter(p, preg, fac, due, "ANC", label, status="no_show", ga=(due - lmp).days / 7)
                late = due + timedelta(days=r.randint(7, 21))
                if r.random() < .55 and late <= ref and late < delivery_date:
                    prev = complete_anc(late)
                    pending_note_for = prev
                elif r.random() < .5:
                    dropped = True
                    break
        if pending_note_for is not None:
            add_anc_note(pending_note_for, None, None)

        # ---- delivery, PNC and child care
        if delivery_date <= ref and (not dropped or r.random() < .5):
            dfac = "F2" if (fac != "F2" and r.random() < .35) else fac
            preg.update(delivery_date=delivery_date, delivery_facility=dfac, delivery_mode=r.choices(
                ["Normal vaginal delivery", "Caesarean section (LSCS)", "Assisted vaginal delivery"],
                weights=[.68, .27, .05])[0])
            self._n["child"] += 1
            child = {"child_key": f"C{self._n['child']:05d}", "mother_key": p["key"], "episode_id": preg["episode_id"],
                     "name": f"Baby of {p['first']}", "sex": r.choice(["Female", "Male"]),
                     "dob": delivery_date, "birth_weight_g": int(_clip(r.gauss(2850, 420), 1600, 4300)),
                     "facility_id": dfac}
            self.c.children.append(child)
            denc = self._encounter(p, preg, dfac, delivery_date, "Delivery", "Delivery", ga=delivery_ga)
            if FAC[dfac]["source_system"] == "ehr_export":
                self._note(denc, "discharge_summary", "Delivery & discharge summary",
                           N.delivery_note(facility=FAC[dfac]["name"], provider=PROV[denc["provider_id"]]["name"],
                                           patient=p, preg=preg, child=child))
            prev = denc
            for days, vtype, prob in PNC_DAYS:
                due = delivery_date + timedelta(days=days)
                self._appointment(p, prev, "PNC visit", vtype, due)
                if due > ref:
                    break
                if r.random() < prob * (.6 + .4 * p_attend):
                    d = min(due + timedelta(days=r.randint(0, 3)), ref)
                    penc = self._encounter(p, preg, dfac, d, "PNC", vtype)
                    o = {"bp_systolic": round(state["sys0"] + r.gauss(0, 5)),
                         "bp_diastolic": round(state["dia0"] + r.gauss(0, 4))}
                    factor = {3: .95, 7: .98}.get(days)
                    o["infant_weight"] = round(child["birth_weight_g"] / 1000 * factor, 2) if factor else round(
                        child["birth_weight_g"] / 1000 + days * .03, 2)
                    for k, v in o.items():
                        self._obs(penc, k, v)
                    if FAC[dfac]["source_system"] == "ehr_export":
                        self._note(penc, "clinical_note", f"{vtype} postnatal note",
                                   N.pnc_note(r, facility=FAC[dfac]["name"], provider=PROV[penc["provider_id"]]["name"],
                                              patient=p, visit=penc, obs=o))
                    prev = penc
            if FAC[dfac]["source_system"] == "ehr_export":
                self._immunizations(p, preg, child, dfac, denc, p_attend)

    def _immunizations(self, p, preg, child, fac, denc, p_attend):
        r, ref = self.rng, self.ref
        prev = denc
        dob = child["dob"]
        for i, (label, days, vaccines, prob) in enumerate(UIP_SCHEDULE):
            due = dob + timedelta(days=days)
            vtype = "Immunization-" + {"Birth": "birth", "6 weeks": "6w", "10 weeks": "10w", "14 weeks": "14w",
                                       "9 months": "9m"}[label]
            if days == 0:
                for v in vaccines:
                    self.c.immunizations.append({"child_key": child["child_key"], "vaccine": v, "schedule": label,
                                                 "due": due, "given": dob, "enc_id": denc["enc_id"]})
                continue
            self._appointment(p, prev, "Immunization", vtype, due, child=child)
            if due > ref:
                for v in vaccines:
                    self.c.immunizations.append({"child_key": child["child_key"], "vaccine": v, "schedule": label,
                                                 "due": due, "given": None, "enc_id": None})
                break
            given_on = None
            if r.random() < prob * (.7 + .3 * p_attend):
                given_on = due + timedelta(days=r.randint(0, 10))
            elif r.random() < .4:
                given_on = due + timedelta(days=r.randint(15, 40))
            if given_on and given_on > ref:
                given_on = None
            enc = None
            if given_on:
                enc = self._encounter(p, preg, fac, given_on, "Child", vtype, child=child,
                                      provider=PAEDIATRICIAN_BY_FACILITY[fac])
                self._obs(enc, "infant_weight", round(child["birth_weight_g"] / 1000 + (given_on - dob).days * .028, 2))
                nxt = UIP_SCHEDULE[i + 1] if i + 1 < len(UIP_SCHEDULE) else None
                self._note(enc, "immunization_record", f"Immunization {label}", N.immunization_note(
                    facility=FAC[fac]["name"], provider=PROV[enc["provider_id"]]["name"], child_name=child["name"],
                    visit=enc, vaccines=vaccines, next_label=nxt[0] if nxt else None,
                    next_due=dob + timedelta(days=nxt[1]) if nxt else None))
                prev = enc
            for v in vaccines:
                self.c.immunizations.append({"child_key": child["child_key"], "vaccine": v, "schedule": label,
                                             "due": due, "given": given_on, "enc_id": enc["enc_id"] if enc else None})
            if not given_on:
                break  # child dropped out of the schedule

    def _note(self, enc: dict, doc_type: str, title: str, text: str):
        self.c.notes.append({"note_id": self._id("note", "N"), "enc_id": enc["enc_id"], "key": enc["key"],
                             "child_key": enc["child_key"], "type": doc_type, "title": title, "date": enc["date"],
                             "author": PROV[enc["provider_id"]]["name"], "text": text,
                             "facility_id": enc["facility_id"]})


def simulate(n_mothers: int = 600, seed: int = 42, reference_date: date | None = None) -> Cohort:
    sim = _Sim(seed, reference_date or date.today())
    for i in range(1, n_mothers + 1):
        sim.simulate_mother(i)
    return sim.c
