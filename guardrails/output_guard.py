"""OUTPUT GUARD - every answer is checked before it reaches the user.

Checks
  O1  clinical-decision language (diagnosis / treatment advice / risk)   lexicon
  O2  grounding: every non-trivial number must appear in the evidence      deterministic
  O3  citations: LLM answers must cite [S#] ids that exist                 deterministic
  O4  personal data: admin-facing answers must contain no identifiers     regex redaction
  O5  NeMo output rails (Colang policy + LLM self-check), LLM answers only
If an LLM answer fails, the orchestrator falls back to the deterministic,
template-based answer (which is safe by construction) - never to an unchecked one.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from guardrails import lexicon as L
from guardrails import pii

_NUM = re.compile(r"(?<![\w\[])(\d+(?:\.\d+)?)(?![\w\]])")
_CITE = re.compile(r"\[S(\d+)\]")


@dataclass
class OutputDecision:
    passed: bool
    action: str                      # pass | fallback | redacted
    text: str
    checks: list[dict] = field(default_factory=list)


MAX_CITES_PER_BULLET = 12
MIN_SUPPORT = 0.5     # share of a statement's content words that must appear in its cited sources
_WORD = re.compile(r"[a-z]{4,}")
_STOP = {"with", "from", "that", "this", "were", "was", "have", "been", "also", "their", "there", "which", "when",
         "patient", "documented", "document", "noted", "recorded", "record", "mentions", "mention", "shows", "show",
         "visit", "visits", "during", "after", "before", "about", "into", "over", "under", "between", "each", "both",
         "they", "them", "then", "than", "some", "such", "made", "done", "given", "listed", "available",
         # common neutral paraphrase vocabulary in MCH records
         "baby", "mother", "received", "receive", "vaccine", "vaccines", "delivered", "deliver", "care", "included",
         "include", "conducted", "underwent", "attended", "female", "male", "child", "weeks", "week", "dated"}


def _stem(w: str) -> str:
    for suf in ("ing", "ed", "es", "s"):
        if w.endswith(suf) and len(w) - len(suf) >= 4:
            return w[: -len(suf)]
    return w


def _support(statement: str, source: str) -> float:
    words = {_stem(w) for w in _WORD.findall(statement.lower())} - {_stem(w) for w in _STOP}
    if len(words) < 3:
        return 1.0
    src = {_stem(w) for w in _WORD.findall(source.lower())}
    return sum(w in src for w in words) / len(words)


def _bullet_checks(text: str, evidence_items: dict[str, str]) -> list[str]:
    """Per-bullet grounding: every bullet cites sources, and its numbers appear in THOSE sources."""
    problems = []
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    bullets = [ln for ln in lines if ln.startswith(("-", "*", "•"))] or lines
    for b in bullets:
        cites = [f"S{c}" for c in _CITE.findall(b)]
        short = b[:60]
        if not cites:
            if _NUM.search(b) or len(b) > 40:
                problems.append(f"uncited statement: '{short}…'")
            continue
        if len(cites) > MAX_CITES_PER_BULLET:
            problems.append(f"{len(cites)} citations on one line (citation dump): '{short}…'")
            continue
        cited_text = " ".join(evidence_items.get(c, "") for c in cites)
        bad = [n for n in _NUM.findall(_CITE.sub("", b)) if (("." in n) or float(n) > 20) and n not in cited_text]
        if bad:
            problems.append(f"value(s) {', '.join(sorted(set(bad))[:4])} not in the cited source(s) {', '.join(cites)}")
        elif _support(_CITE.sub("", b), cited_text) < MIN_SUPPORT:
            problems.append(f"statement not supported by its cited source(s) {', '.join(cites)}: '{short}…'")
    return problems


def check(text: str, *, evidence_text: str, evidence_ids: set[str], role: str, generated_by: str,
          user_text: str = "", nemo=None, evidence_items: dict[str, str] | None = None) -> OutputDecision:
    checks, failed = [], False

    hits = L.find(L.OUTPUT_PATTERNS, text)
    checks.append({"check": "O1 Clinical-decision language", "verdict": "fail" if hits else "pass",
                   "detail": "; ".join(f"{c}: '{m}'" for c, m in hits) or "none"})
    failed |= bool(hits)

    if generated_by == "llm":
        ev = evidence_text
        ungrounded = [n for n in _NUM.findall(text) if (("." in n) or float(n) > 20) and n not in ev]
        checks.append({"check": "O2 Numeric grounding", "verdict": "fail" if ungrounded else "pass",
                       "detail": ("not in evidence: " + ", ".join(sorted(set(ungrounded))[:6])) if ungrounded
                       else "all values traceable to evidence"})
        failed |= bool(ungrounded)
        cites = set(_CITE.findall(text))
        bad = [c for c in cites if f"S{c}" not in evidence_ids]
        ok = bool(cites) and not bad
        checks.append({"check": "O3 Citations", "verdict": "pass" if ok else "fail",
                       "detail": f"{len(cites)} cited" + (f"; unknown: {bad}" if bad else "") if cites else "no citations"})
        failed |= not ok
        if evidence_items:
            probs = _bullet_checks(text, evidence_items)
            checks.append({"check": "O3b Per-statement attribution", "verdict": "fail" if probs else "pass",
                           "detail": "; ".join(probs[:3]) or "every statement cites the source containing its values"})
            failed |= bool(probs)
    else:
        checks.append({"check": "O2/O3 Grounding & citations", "verdict": "pass",
                       "detail": "deterministic template built directly from records"})

    out = text
    action = "pass"
    if role == "admin":
        red = pii.redact(text, ("phone", "email", "id_number", "patient_id"))
        if red != text:
            out, action = red, "redacted"
        checks.append({"check": "O4 Personal data (admin view)", "verdict": "redacted" if red != text else "pass",
                       "detail": "identifiers removed" if red != text else "no identifiers"})
    else:
        checks.append({"check": "O4 Personal data", "verdict": "pass", "detail": f"role '{role}' authorised"})

    if generated_by == "llm" and nemo is not None and nemo.status in ("ready", "ready_offline") and not failed:
        res = nemo.check_output(user_text, text)
        blocked = res["status"] == "blocked"
        checks.append({"check": "O5 NeMo output rails", "verdict": "fail" if blocked else "pass",
                       "detail": f"status={res['status']}" + (f"; rail='{res['rail']}'" if res.get("rail") else "")})
        failed |= blocked

    if failed:
        return OutputDecision(False, "fallback", out, checks)
    return OutputDecision(True, action, out, checks)
