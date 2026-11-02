"""Free-text translation (English -> Hindi / Bengali / Kannada) for the doctor's verified note.

Order of preference:
  1. AI4Bharat IndicTrans2 (open-source, best quality for Indic languages) - USE_INDICTRANS=true,
     model `ai4bharat/indictrans2-en-indic-dist-200M` (needs torch + transformers + IndicTransToolkit)
  2. the open-source chat LLM - ONLY if ALLOW_LLM_TRANSLATION=true. Off by default: in testing,
     qwen2.5-7B translated "Pregnancy" as "marriage" and "Delivery" as "expulsion" in Hindi.
  3. no translation -> the report keeps the verified English note, labelled in the patient's language
Machine-translated text is always shown next to the verified English original.
"""
from __future__ import annotations

import logging
from functools import lru_cache

from ai.llm.client import LLMUnavailable, get_llm
from common.settings import get_settings

log = logging.getLogger("cliniesync.translate")
FLORES = {"hi": "hin_Deva", "bn": "ben_Beng", "kn": "kan_Knda"}
NAMES = {"hi": "Hindi", "bn": "Bengali", "kn": "Kannada"}


@lru_cache
def _indictrans():  # pragma: no cover - heavy optional dependency
    import torch
    from IndicTransToolkit import IndicProcessor
    from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

    name = "ai4bharat/indictrans2-en-indic-dist-200M"
    tok = AutoTokenizer.from_pretrained(name, trust_remote_code=True)
    model = AutoModelForSeq2SeqLM.from_pretrained(name, trust_remote_code=True)
    model = model.to("cuda" if torch.cuda.is_available() else "cpu").eval()
    return tok, model, IndicProcessor(inference=True)


def _translate_indictrans(text: str, lang: str) -> str:  # pragma: no cover
    import torch

    tok, model, ip = _indictrans()
    sents = [s for s in text.split("\n") if s.strip()]
    batch = ip.preprocess_batch(sents, src_lang="eng_Latn", tgt_lang=FLORES[lang])
    enc = tok(batch, padding="longest", truncation=True, return_tensors="pt").to(model.device)
    with torch.no_grad():
        out = model.generate(**enc, max_length=256, num_beams=4)
    dec = tok.batch_decode(out, skip_special_tokens=True)
    return "\n".join(ip.postprocess_batch(dec, lang=FLORES[lang]))


def translate(text: str, lang: str) -> tuple[str | None, str]:
    """Return (translated text or None, engine name)."""
    if lang == "en" or not text.strip():
        return text, "none"
    if get_settings().use_indictrans:
        try:
            return _translate_indictrans(text, lang), "IndicTrans2"
        except Exception as exc:
            log.warning("IndicTrans2 unavailable: %s", exc)
    llm = get_llm()
    if get_settings().allow_llm_translation and llm.available():
        try:
            out = llm.chat([
                {"role": "system", "content": f"Translate the user's text from English to {NAMES[lang]}. Output only the "
                                              "translation. Keep numbers, dates, names and medical test names unchanged. "
                                              "Do not add or remove information."},
                {"role": "user", "content": text}], max_tokens=800)
            return out, f"LLM ({llm.model})"
        except LLMUnavailable:
            pass
    return None, "unavailable"
