"""Server-side speech-to-text (English) for voice queries.

Primary path in the UI is the browser's Web Speech API (lang en-IN), which
needs no server. This module is the offline / privacy-preserving alternative:
open-source Whisper via `faster-whisper` (pip install faster-whisper), running
on the clinic's own GPU/CPU so audio never leaves the premises.
"""
from __future__ import annotations

import os
import tempfile
from functools import lru_cache


class STTUnavailable(RuntimeError):
    pass


@lru_cache
def _model():
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise STTUnavailable("faster-whisper is not installed (pip install faster-whisper)") from exc
    size = os.getenv("WHISPER_MODEL", "small.en")
    device = os.getenv("WHISPER_DEVICE", "auto")
    return WhisperModel(size, device=device, compute_type="int8")


def available() -> bool:
    try:
        import faster_whisper  # noqa: F401

        return True
    except ImportError:
        return False


def transcribe(audio_bytes: bytes, suffix: str = ".webm") -> dict:
    model = _model()
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=True) as f:
        f.write(audio_bytes)
        f.flush()
        segments, info = model.transcribe(f.name, language="en", vad_filter=True,
                                          initial_prompt="ANC, PNC, follow-up, haemoglobin, OGTT, CS-000123")
        text = " ".join(s.text.strip() for s in segments)
    return {"text": text.strip(), "language": info.language, "duration_s": round(info.duration, 1)}
