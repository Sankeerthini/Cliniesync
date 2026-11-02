"""Custom NeMo Guardrails actions (auto-registered from the config folder).

They call the same deterministic policy used by ClinieSync's own guard layers,
so NeMo and the native pipeline can never disagree on what is allowed.
"""
from typing import Optional

from nemoguardrails.actions import action


@action(name="cliniesync_input_policy")
async def cliniesync_input_policy(context: Optional[dict] = None) -> bool:
    from guardrails.input_guard import deterministic_verdict

    text = (context or {}).get("user_message") or ""
    category, _ = deterministic_verdict(text)
    return category is None


@action(name="cliniesync_output_policy")
async def cliniesync_output_policy(context: Optional[dict] = None) -> bool:
    from guardrails.lexicon import OUTPUT_PATTERNS, find

    text = (context or {}).get("bot_message") or ""
    return not find(OUTPUT_PATTERNS, text)
