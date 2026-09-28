"""Optional live check of the Gemini adapter — owner-run only.

Deselected by default (``addopts = -m 'not live'``). Run explicitly with
``uv run --env-file .env pytest -m live tests/test_gemini_live.py``. It sends ONE synthetic,
non-assessment prompt to the configured primary model and needs ``GOOGLE_API_KEY``.
"""

from __future__ import annotations

import pytest

from support_agent.config import ConfigError, Settings
from support_agent.llm import FinalAnswer, LLMRequest, UserMessage
from support_agent.llm.gemini import GeminiClient

pytestmark = pytest.mark.live

SYSTEM = (
    "You are a support assistant for the FICTIONAL demo store 'Acme Pay Demo'. "
    "Policy P1: installments are due every 14 days. Answer in one short sentence."
)


def test_live_single_synthetic_call() -> None:
    try:
        settings = Settings.from_env()
    except ConfigError as exc:
        pytest.skip(f"live test not configured: {exc}")
    if settings.provider != "gemini" or settings.api_key is None:
        pytest.skip("live test needs LLM_PROVIDER=gemini and GOOGLE_API_KEY")
    client = GeminiClient(settings)
    resp = client.generate(
        LLMRequest(
            system=SYSTEM,
            contents=(UserMessage("How often are installments due at the demo store?"),),
            tool_mode="none",
        )
    )
    assert resp.final_json is not None, resp.finish_reason
    FinalAnswer.model_validate(resp.final_json)
    assert resp.usage.input > 0
    assert [a.status for a in resp.attempts][-1] == "ok"
