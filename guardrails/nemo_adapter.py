"""NVIDIA NeMo Guardrails integration.

The rails configuration lives in `guardrails/nemo_config/`:
  * `cliniesync input policy`  - Colang flow calling our deterministic policy action
                                 (works offline, no LLM needed)
  * `self check input`         - NeMo's LLM-based self-check with a ClinieSync prompt
                                 (enabled automatically when the open-source LLM is reachable)
  * `cliniesync output policy` / `self check output` - the same for generated answers

NeMo runs on its own background event loop so it can be called safely from
FastAPI worker threads.
"""
from __future__ import annotations

import asyncio
import logging
import threading
from pathlib import Path

from common.settings import get_settings

log = logging.getLogger("cliniesync.nemo")
CONFIG_DIR = Path(__file__).parent / "nemo_config"


class NemoGuardrails:
    def __init__(self):
        self.status = "not_loaded"      # not_loaded | ready | ready_offline | disabled | error
        self.error: str | None = None
        self.llm_rails_active = False
        self._rails = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._lock = threading.Lock()

    # ------------------------------------------------------------------ setup
    def _ensure_loop(self):
        if self._loop is None:
            self._loop = asyncio.new_event_loop()
            threading.Thread(target=self._loop.run_forever, name="nemo-guardrails", daemon=True).start()

    def load(self, llm_available: bool) -> None:
        s = get_settings()
        if not s.use_nemo_guardrails:
            self.status = "disabled"
            return
        with self._lock:
            if self._rails is not None and self.llm_rails_active == llm_available:
                return
            try:
                from nemoguardrails import LLMRails, RailsConfig

                config = RailsConfig.from_path(str(CONFIG_DIR))
                for m in config.models:
                    m.model = s.llm_model
                    m.parameters = {**(m.parameters or {}), "base_url": s.llm_base_url}
                if not llm_available:   # keep only deterministic Colang rails
                    config.rails.input.flows = [f for f in config.rails.input.flows if not f.startswith("self check")]
                    config.rails.output.flows = [f for f in config.rails.output.flows if not f.startswith("self check")]
                self._ensure_loop()
                self._rails = LLMRails(config)
                self.llm_rails_active = llm_available
                self.status = "ready" if llm_available else "ready_offline"
                self.error = None
            except Exception as exc:  # pragma: no cover - environment dependent
                self._rails = None
                self.status = "error"
                self.error = f"{type(exc).__name__}: {exc}"
                log.warning("NeMo Guardrails unavailable: %s", self.error)

    def describe(self) -> dict:
        flows_in = flows_out = []
        if self._rails is not None:
            flows_in = list(self._rails.config.rails.input.flows)
            flows_out = list(self._rails.config.rails.output.flows)
        return {"status": self.status, "error": self.error, "llm_self_check": self.llm_rails_active,
                "input_flows": flows_in, "output_flows": flows_out}

    # ------------------------------------------------------------------ checks
    def _run(self, messages: list[dict], timeout: float = 30.0) -> dict:
        if self._rails is None:
            return {"status": "skipped", "rail": None}
        fut = asyncio.run_coroutine_threadsafe(self._rails.check_async(messages), self._loop)
        try:
            res = fut.result(timeout=timeout)
        except Exception as exc:
            log.warning("NeMo check failed: %s", exc)
            # Fail closed only for the deterministic policy; an LLM outage should not block all traffic.
            return {"status": "error", "rail": None, "error": str(exc)}
        return {"status": res.status.value, "rail": res.rail}

    def check_input(self, text: str) -> dict:
        return self._run([{"role": "user", "content": text}])

    def check_output(self, user_text: str, bot_text: str) -> dict:
        return self._run([{"role": "user", "content": user_text}, {"role": "assistant", "content": bot_text}])


_nemo: NemoGuardrails | None = None


def get_nemo() -> NemoGuardrails:
    global _nemo
    if _nemo is None:
        _nemo = NemoGuardrails()
    return _nemo
