"""Catalogue of the clinical parameters and tests a user can ask about (as documented, never interpreted).

Used in two places:
  * retrieval - maps "haemoglobin", "BP", "OGTT", "baby's weight"... to observation codes (visit readings)
    and investigation codes (lab / imaging reports), so every parameter is answered the same way;
  * guardrails - `mask()` replaces parameter names with a neutral token before the semantic intent screen,
    so the screen judges the *framing* of a request ("show her X readings" vs "is her X normal"),
    not the test it mentions.
"""
from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Parameter:
    key: str
    label: str
    pattern: re.Pattern
    observation_codes: tuple[str, ...] = ()
    investigation_codes: tuple[str, ...] = ()


def _p(rx: str) -> re.Pattern:
    return re.compile(rx, re.I)


_INFANT_WEIGHT = _p(r"\b((infant|baby|babies|child|children|newborn|neonat\w*)'?s?\s+(birth\s*)?weights?|birth\s*weights?|"
                    r"weights? of (the |her )?(baby|infant|child|newborn))\b")

PARAMETERS: tuple[Parameter, ...] = (
    Parameter("haemoglobin", "Haemoglobin", _p(r"\b(ha?emoglobins?|hb|hgb)\b"), ("hemoglobin",), ("cbc",)),
    Parameter("blood_pressure", "Blood pressure", _p(r"\b(blood pressures?|bps?|systolic|diastolic)\b"),
              ("bp_systolic", "bp_diastolic")),
    Parameter("infant_weight", "Infant weight", _INFANT_WEIGHT, ("infant_weight",)),
    Parameter("weight", "Body weight", _p(r"\b(body |maternal |her |mother'?s? )?weights?\b"), ("weight",)),
    Parameter("fundal_height", "Fundal height", _p(r"\b(fundal heights?|sfh|symphysis[- ]fundal\w*)\b"), ("fundal_height",)),
    Parameter("fetal_heart_rate", "Fetal heart rate", _p(r"\b(fo?etal heart( rates?| sounds?)?|fhr|fhs|heart rates?)\b"),
              ("fetal_heart_rate",)),
    Parameter("urine", "Urine albumin / urine routine", _p(r"\b(urine( albumin| protein| sugar| routine| tests?)?|albumin|"
                                                           r"proteinuria)\b"), ("urine_albumin",), ("urine_routine",)),
    Parameter("glucose", "Blood glucose (OGTT)", _p(r"\b(blood sugars?|sugars?|glucose|o?gtt)\b"), (), ("ogtt",)),
    Parameter("cbc", "Complete blood count", _p(r"\b(cbc|complete blood counts?|blood counts?|platelets?( counts?)?|"
                                                r"wbc|tlc)\b"), (), ("cbc",)),
    Parameter("thyroid", "TSH (thyroid)", _p(r"\b(tsh|thyroid( function)?( tests?)?)\b"), (), ("tsh",)),
    Parameter("hiv", "HIV screening", _p(r"\bhiv\b"), (), ("hiv",)),
    Parameter("syphilis", "Syphilis screening (VDRL/RPR)", _p(r"\b(vdrl|rpr|syphilis)\b"), (), ("vdrl",)),
    Parameter("hbsag", "HBsAg", _p(r"\b(hbsag|hepatitis[- ]?b)\b"), (), ("hbsag",)),
    Parameter("blood_group", "Blood group & Rh", _p(r"\b(blood groups?|blood typ\w*|rh( typing| factor)?)\b"), (),
              ("blood_group",)),
    Parameter("ultrasound", "Obstetric ultrasound", _p(r"\b(ultrasounds?|usgs?|scans?|sonograph\w*)\b"), (),
              ("usg_dating", "usg_anomaly", "usg_growth")),
)
BY_KEY = {p.key: p for p in PARAMETERS}
GENERIC_VALUES = _p(r"\b(readings?|vitals?|measurements?|values?|trends?|parameters?)\b")
DEFAULT_KEYS = ("weight", "blood_pressure", "haemoglobin")      # "show her vitals / readings"

_MASK = re.compile("|".join(f"(?:{p.pattern.pattern})" for p in PARAMETERS) + r"|\bvitals?\b", re.I)


def detect(text: str) -> list[Parameter]:
    """Parameters named in the text, in catalogue order (infant weight takes precedence over body weight)."""
    found = []
    rest = text
    if _INFANT_WEIGHT.search(text):
        found.append(BY_KEY["infant_weight"])
        rest = _INFANT_WEIGHT.sub(" ", text)
    for p in PARAMETERS:
        if p.key != "infant_weight" and p.pattern.search(rest):
            found.append(p)
    return found


def mask(text: str) -> str:
    """Replace parameter / test names with a neutral token (for the semantic intent screen)."""
    return _MASK.sub(" xparam ", text)


TERMS = _MASK.pattern     # every parameter / test name, for guardrail patterns
