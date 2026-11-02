"""Template-based synthetic clinical notes (unstructured text).

Notes imitate the style of Indian OPD documentation (abbreviations such as
G2P1, c/o, FH, FHR) so the ETL and RAG layers are exercised on realistic text.
They contain DOCUMENTED information only and are entirely fictional.
"""
from __future__ import annotations

import random
from datetime import date


def _ga(ga_weeks: float) -> str:
    w = int(ga_weeks)
    d = int(round((ga_weeks - w) * 7))
    if d == 7:
        w, d = w + 1, 0
    return f"{w}w{d}d"


def anc_note(rng: random.Random, *, facility: str, provider: str, patient: dict, preg: dict, visit: dict,
             obs: dict, tests: list[str], next_due: date | None, next_label: str | None, complaint: str) -> str:
    lines = [
        f"ANTENATAL VISIT NOTE - {facility}",
        f"Date: {visit['date'].strftime('%d/%m/%Y')}    Seen by: {provider}",
        f"Name: {patient['name']}  Age: {patient['age']}y  G{preg['gravida']}P{preg['parity']}  "
        f"LMP: {preg['lmp'].strftime('%d/%m/%Y')}  EDD: {preg['edd'].strftime('%d/%m/%Y')}",
        f"Visit: {visit['vtype']}   POG: {_ga(visit['ga'])}",
        f"c/o: {complaint}.",
    ]
    o = [f"Wt {obs['weight']:.1f} kg", f"BP {obs['bp_systolic']:.0f}/{obs['bp_diastolic']:.0f} mmHg"]
    if "fundal_height" in obs:
        o.append(f"FH {obs['fundal_height']:.0f} cm")
    if "fetal_heart_rate" in obs:
        o.append(f"FHR {obs['fetal_heart_rate']:.0f}/min")
    o.append(f"Urine albumin {obs.get('urine_albumin', 'Nil')}")
    lines.append("O/E: " + ", ".join(o) + ".")
    if tests:
        lines.append("Investigations sent: " + ", ".join(tests) + ".")
    plan = rng.choice([
        "IFA and calcium continued as per programme protocol.",
        "Counselled on danger signs and birth preparedness as per MCP card.",
        "MCP card updated. Diet counselling given.",
    ])
    lines.append("Plan: " + plan)
    if next_due:
        style = rng.random()
        if style < .5:
            lines.append(f"Next ANC visit on {next_due.strftime('%d/%m/%Y')} ({next_label}).")
        elif style < .8:
            weeks = max(1, round((next_due - visit["date"]).days / 7))
            lines.append(f"Review after {weeks} weeks for {next_label}.")
        else:
            lines.append(f"Follow-up: {next_label} due {next_due.strftime('%d-%b-%Y')}.")
    if tests and rng.random() < .55:
        lines.append("Review after 2 weeks with investigation reports.")
    return "\n".join(lines)


def delivery_note(*, facility: str, provider: str, patient: dict, preg: dict, child: dict) -> str:
    return "\n".join([
        f"DELIVERY / DISCHARGE SUMMARY - {facility}",
        f"Name: {patient['name']}  Age: {patient['age']}y  G{preg['gravida']}P{preg['parity']}",
        f"Date of delivery: {preg['delivery_date'].strftime('%d/%m/%Y')}    Attending: {provider}",
        f"Mode of delivery (documented): {preg['delivery_mode']}. POG at delivery: {_ga(preg['delivery_ga'])}.",
        f"Baby: live {child['sex'].lower()} baby, birth weight {child['birth_weight_g']} g.",
        "Birth-dose vaccines given as per UIP schedule (BCG, OPV-0, Hep B).",
        "Discharged with MCP card. Postnatal check-ups scheduled on day 3, day 7 and day 42.",
    ])


def pnc_note(rng: random.Random, *, facility: str, provider: str, patient: dict, visit: dict, obs: dict) -> str:
    feeding = rng.choice(["Exclusive breastfeeding established.", "Breastfeeding well, counselled on positioning."])
    return "\n".join([
        f"POSTNATAL VISIT NOTE - {facility}",
        f"Date: {visit['date'].strftime('%d/%m/%Y')}    Seen by: {provider}",
        f"Name: {patient['name']}  Visit: {visit['vtype']}",
        f"Mother: BP {obs['bp_systolic']:.0f}/{obs['bp_diastolic']:.0f} mmHg. {feeding}",
        f"Baby weight {obs.get('infant_weight', 0):.2f} kg." if obs.get("infant_weight") else "Baby reviewed.",
        "Family planning counselling documented.",
    ])


def immunization_note(*, facility: str, provider: str, child_name: str, visit: dict, vaccines: list[str],
                      next_label: str | None, next_due: date | None) -> str:
    lines = [
        f"IMMUNIZATION RECORD - {facility}",
        f"Date: {visit['date'].strftime('%d/%m/%Y')}    By: {provider}",
        f"Child: {child_name}   Session: {visit['vtype'].replace('Immunization-', '')}",
        "Vaccines given: " + ", ".join(vaccines) + ".",
    ]
    if next_due:
        lines.append(f"Next due: {next_label} on {next_due.strftime('%d/%m/%Y')}.")
    return "\n".join(lines)
