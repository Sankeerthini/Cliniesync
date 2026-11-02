"""INPUT GUARD - screens every query (typed or spoken) before any data is touched.

Layers (all logged in the guard trace shown to the user):
  L1  normalisation + length check
  L2  personal-data scan (flag + redact in logs; not a block)
  L3  prompt-injection / bulk-export patterns              -> block
  L4  clinical-decision lexicon (diagnosis, treatment,
      advice, risk scoring) + out-of-scope                 -> block / decline
  L5  semantic similarity to blocked exemplars             -> block
  L6  NVIDIA NeMo Guardrails (Colang policy + LLM self-check)-> block
Fail-closed: any layer that blocks wins.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from ai.router.intent_classifier import ALLOWED, classify, semantic_scores
from guardrails import lexicon as L
from guardrails import pii

MAX_LEN = 1000
PRIORITY = ["prompt_injection", "bulk_data_export", "risk_scoring", "treatment_prescription", "clinical_advice",
            "diagnosis", "out_of_scope"]
SEMANTIC_BLOCK_THRESHOLD = 0.50
SEMANTIC_MARGIN = 0.08
OUT_OF_SCOPE_FLOOR = 0.16


@dataclass
class InputDecision:
    allowed: bool
    intent: str                     # allowed intent, or blocked category
    category: str | None            # blocked category (None when allowed)
    confidence: float
    layers: list[dict] = field(default_factory=list)
    pii_found: list[str] = field(default_factory=list)
    redacted_query: str = ""


def _lexicon(text: str) -> list[tuple[str, str]]:
    hits = L.find(L.INPUT_PATTERNS, text)
    if L.SOFT_TREATMENT_WORDS.search(text) and not L.DOCUMENTATION_FRAMING.search(text) \
            and not any(c == "treatment_prescription" for c, _ in hits):
        hits.append(("treatment_prescription", L.SOFT_TREATMENT_WORDS.search(text).group(0) +
                     " (not framed as retrieval of documented records)"))
    return hits


def _semantic_block(text: str) -> tuple[str | None, list[tuple[str, float]]]:
    scores = semantic_scores(text)
    best_allowed = max((s for k, s in scores if k in ALLOWED), default=0.0)
    top, top_score = scores[0]
    if top not in ALLOWED and top != "out_of_scope" and top_score >= SEMANTIC_BLOCK_THRESHOLD \
            and top_score - best_allowed >= SEMANTIC_MARGIN:
        return top, scores
    return None, scores


def deterministic_verdict(text: str) -> tuple[str | None, list[dict]]:
    """Layers L1-L5. Returns (blocked category or None, layer trace)."""
    layers = []
    t = re.sub(r"\s+", " ", text or "").strip()
    if not t:
        return "out_of_scope", [{"layer": "L1 Normalisation", "verdict": "block", "detail": "empty query"}]
    if len(t) > MAX_LEN:
        layers.append({"layer": "L1 Normalisation", "verdict": "block", "detail": f"query longer than {MAX_LEN} chars"})
        return "prompt_injection", layers
    layers.append({"layer": "L1 Normalisation", "verdict": "pass", "detail": f"{len(t)} chars"})

    found = pii.detect(t)
    layers.append({"layer": "L2 Personal-data scan", "verdict": "flag" if found else "pass",
                   "detail": ("contains " + ", ".join(found) + " - redacted in logs") if found else "none detected"})

    hits = _lexicon(t)
    sec = [h for h in hits if h[0] in ("prompt_injection", "bulk_data_export")]
    layers.append({"layer": "L3 Injection & data-exfiltration rules", "verdict": "block" if sec else "pass",
                   "detail": "; ".join(f"{c}: '{m}'" for c, m in sec) or "no match"})
    clin = [h for h in hits if h[0] not in ("prompt_injection", "bulk_data_export")]
    layers.append({"layer": "L4 Clinical-decision lexicon", "verdict": "block" if clin else "pass",
                   "detail": "; ".join(f"{c}: '{m}'" for c, m in clin) or "no diagnosis/treatment/advice/risk terms"})

    sem_cat, scores = _semantic_block(t)
    top3 = ", ".join(f"{k} {v:.2f}" for k, v in scores[:3])
    layers.append({"layer": "L5 Semantic intent screen", "verdict": "block" if sem_cat else "pass",
                   "detail": f"nearest: {top3}"})

    cats = [c for c, _ in hits] + ([sem_cat] if sem_cat else [])
    if not cats:
        best_allowed = max((s for k, s in scores if k in ALLOWED), default=0.0)
        if best_allowed < OUT_OF_SCOPE_FLOOR and not any(rx.search(t) for _, rx in _allowed_rules()):
            cats.append("out_of_scope")
            layers[-1]["verdict"] = "decline"
            layers[-1]["detail"] += " (no workflow intent recognised)"
    for p in PRIORITY:
        if p in cats:
            return p, layers
    return None, layers


def _allowed_rules():
    from ai.router.intent_classifier import RULES

    return RULES


class InputGuard:
    def __init__(self, nemo=None):
        self.nemo = nemo

    def check(self, text: str, has_patient_context: bool = False) -> InputDecision:
        category, layers = deterministic_verdict(text)
        if self.nemo is not None and self.nemo.status in ("ready", "ready_offline"):
            res = self.nemo.check_input(text)
            blocked = res["status"] == "blocked"
            layers.append({"layer": "L6 NVIDIA NeMo Guardrails", "verdict": "block" if blocked else "pass",
                           "detail": f"rails={'Colang policy + LLM self-check' if self.nemo.llm_rails_active else 'Colang policy (offline)'}; "
                                     f"status={res['status']}" + (f"; rail='{res['rail']}'" if res.get("rail") else "")})
            if blocked and category is None:
                category = "clinical_advice" if res.get("rail", "").startswith("self check") else "diagnosis"
        else:
            layers.append({"layer": "L6 NVIDIA NeMo Guardrails", "verdict": "skipped",
                           "detail": "NeMo not loaded" if self.nemo is None else f"status={self.nemo.status}"})
        redacted = pii.redact(text)
        found = pii.detect(text)
        if category:
            return InputDecision(False, category, category, 1.0, layers, found, redacted)
        ir = classify(text, has_patient_context)
        layers.append({"layer": "Intent router", "verdict": "route",
                       "detail": f"{ir.intent} ({ir.method}, confidence {ir.confidence:.2f})"})
        return InputDecision(True, ir.intent, None, ir.confidence, layers, found, redacted)
