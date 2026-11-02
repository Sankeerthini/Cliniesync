"""Thin client for any OpenAI-compatible chat endpoint serving an OPEN-SOURCE model.

Default: Ollama (http://localhost:11434/v1) with `qwen2.5:7b-instruct`.
Also works unchanged with vLLM, llama.cpp server, LM Studio or TGI.

Every caller must handle `LLMUnavailable` - ClinieSync is designed so that
each AI feature has a deterministic fallback and the demo never depends on
the model being up.
"""
from __future__ import annotations

import json
import logging
import re
import time

import httpx

from common.settings import get_settings

log = logging.getLogger("cliniesync.llm")
_THINK = re.compile(r"<think>.*?</think>", re.S)


class LLMUnavailable(RuntimeError):
    pass


class LLMClient:
    def __init__(self):
        self.s = get_settings()
        self._health: tuple[float, bool] = (0.0, False)

    @property
    def model(self) -> str:
        return self.s.llm_model

    def available(self) -> bool:
        if not self.s.llm_enabled:
            return False
        ts, ok = self._health
        if time.time() - ts < 30:
            return ok
        try:
            r = httpx.get(f"{self.s.llm_base_url}/models", timeout=2.0,
                          headers={"Authorization": f"Bearer {self.s.llm_api_key}"})
            ok = r.status_code == 200
        except Exception:
            ok = False
        self._health = (time.time(), ok)
        return ok

    def chat(self, messages: list[dict], *, model: str | None = None, temperature: float = 0.0,
             max_tokens: int = 700, json_mode: bool = False) -> str:
        if not self.available():
            raise LLMUnavailable("LLM endpoint not reachable")
        body = {"model": model or self.s.llm_model, "messages": messages, "temperature": temperature,
                "max_tokens": max_tokens, "stream": False}
        if json_mode:
            body["response_format"] = {"type": "json_object"}
        try:
            r = httpx.post(f"{self.s.llm_base_url}/chat/completions", json=body, timeout=self.s.llm_timeout_s,
                           headers={"Authorization": f"Bearer {self.s.llm_api_key}"})
            r.raise_for_status()
            text = r.json()["choices"][0]["message"]["content"] or ""
        except Exception as exc:
            self._health = (time.time(), False)
            raise LLMUnavailable(str(exc)) from exc
        return _THINK.sub("", text).strip()

    def chat_json(self, messages: list[dict], **kw) -> dict:
        raw = self.chat(messages, json_mode=True, **kw)
        m = re.search(r"\{.*\}", raw, re.S)
        if not m:
            raise ValueError(f"LLM did not return JSON: {raw[:200]}")
        return json.loads(m.group())


_client: LLMClient | None = None


def get_llm() -> LLMClient:
    global _client
    if _client is None:
        _client = LLMClient()
    return _client
