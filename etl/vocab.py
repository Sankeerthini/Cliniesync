"""Controlled vocabulary: local source terms -> canonical ClinieSync codes.

Extend these dictionaries when onboarding a new clinic; every unmapped term
is reported in the data-quality report instead of being silently dropped.
"""
from __future__ import annotations

import re

from data_generator.reference import OBS_CODES, TESTS

# observation name -> canonical code (keys are normalised: lower-case, alnum only)
OBS_SYNONYMS = {
    "wt": "weight", "weight": "weight", "weightkg": "weight", "bodyweight": "weight",
    "hb": "hemoglobin", "haemoglobin": "hemoglobin", "hemoglobin": "hemoglobin",
    "fh": "fundal_height", "fundalht": "fundal_height", "fundalheight": "fundal_height",
    "fhr": "fetal_heart_rate", "fhs": "fetal_heart_rate", "fetalheartrate": "fetal_heart_rate",
    "urinealbumin": "urine_albumin", "urinealb": "urine_albumin",
    "babywt": "infant_weight", "infantweight": "infant_weight",
    "bpsystolic": "bp_systolic", "sbp": "bp_systolic", "bpdiastolic": "bp_diastolic", "dbp": "bp_diastolic",
    "bp": "bp_combined", "bloodpressure": "bp_combined",
}

# test name -> canonical test code (built from the reference variants + extras)
TEST_SYNONYMS = {}
for _code, (_display, _cat, _variants) in TESTS.items():
    for _v in _variants + [_display]:
        TEST_SYNONYMS[re.sub(r"[^a-z0-9]", "", _v.lower())] = _code

ENCOUNTER_TYPE = {
    "anc": "ANC", "antenatalvisit": "ANC", "ancfollowup": "ANC", "antenatal": "ANC",
    "delivery": "Delivery", "ipdelivery": "Delivery",
    "pnc": "PNC", "postnatalvisit": "PNC", "postnatal": "PNC",
    "immunisation": "Child", "immunization": "Child", "immunizationclinic": "Child", "immunisationclinic": "Child",
}
ENCOUNTER_STATUS = {"completed": "completed", "seen": "completed", "noshow": "no_show", "dna": "no_show",
                    "didnotattend": "no_show"}

LANGUAGE = {"kannada": "kn", "hindi": "hi", "bengali": "bn", "bangla": "bn", "english": "en",
            "kn": "kn", "hi": "hi", "bn": "bn", "en": "en"}

PNC_LABELS = [(3, "PNC-D3"), (7, "PNC-D7"), (42, "PNC-D42")]
IMMUNIZATION_SESSIONS = [(0, "Immunization-birth", "Birth"), (42, "Immunization-6w", "6 weeks"),
                         (70, "Immunization-10w", "10 weeks"), (98, "Immunization-14w", "14 weeks"),
                         (270, "Immunization-9m", "9 months")]
SESSION_BY_LABEL = {"Birth": "Immunization-birth", "6 weeks": "Immunization-6w", "10 weeks": "Immunization-10w",
                    "14 weeks": "Immunization-14w", "9 months": "Immunization-9m",
                    "6w": "Immunization-6w", "10w": "Immunization-10w", "14w": "Immunization-14w",
                    "9m": "Immunization-9m", "birth": "Immunization-birth"}

# Plausibility ranges: DATA-QUALITY checks only (catch typos like 520 kg), never clinical interpretation.
PLAUSIBLE = {
    "weight": (30, 150), "bp_systolic": (60, 220), "bp_diastolic": (30, 140), "hemoglobin": (3, 20),
    "fundal_height": (5, 50), "fetal_heart_rate": (80, 220), "infant_weight": (0.5, 15),
}


def key(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(s).lower())


def obs_display(code: str) -> tuple[str, str | None, str | None]:
    return OBS_CODES.get(code, (code, None, None))


def test_display(code: str) -> tuple[str, str]:
    display, cat, _ = TESTS[code]
    return display, cat


def appointment_type(purpose: str) -> tuple[str, str | None]:
    """Map a free-text appointment purpose to (followup_type, expected visit label)."""
    p = purpose.lower()
    if "report" in p or "lab" in p:
        return "Investigation review", None
    if "pnc" in p or "postnatal" in p:
        m = re.search(r"d(\d+)", p.replace(" ", ""))
        return "PNC visit", f"PNC-D{m.group(1)}" if m else None
    if "immuni" in p or "vaccin" in p:
        m = re.search(r"(birth|\d+w|\d+m)\b", p)
        return "Immunization", SESSION_BY_LABEL.get(m.group(1)) if m else None
    return "ANC visit", None
