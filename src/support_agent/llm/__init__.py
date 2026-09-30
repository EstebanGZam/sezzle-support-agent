"""LLM clients behind one provider-agnostic protocol (architecture §3.4, §7, §8)."""

from __future__ import annotations

from support_agent.config import Settings
from support_agent.llm.base import (
    ERROR_CLASSES,
    ESCALATION_REASONS,
    RETRY_TABLE,
    AttemptRecord,
    AttemptRunner,
    AuthBillingError,
    FinalAnswer,
    FunctionCall,
    LLMClient,
    LLMRequest,
    LLMResponse,
    Message,
    ModelTurn,
    ProviderError,
    ToolMode,
    ToolResult,
    Usage,
    UserMessage,
    final_answer_json_schema,
)
from support_agent.llm.fake import DEFAULT_FAKE_ANSWER, FakeLLM, FakeScriptExhausted


def make_llm_client(settings: Settings) -> LLMClient:
    """The client for ``settings.provider``; provider modules are imported only when needed."""
    if settings.provider == "fake":
        return FakeLLM.from_settings(settings)
    if settings.provider == "groq":
        from support_agent.llm.groq import GroqClient

        return GroqClient(settings)
    from support_agent.llm.gemini import GeminiClient

    return GeminiClient(settings)


__all__ = [
    "DEFAULT_FAKE_ANSWER",
    "ERROR_CLASSES",
    "ESCALATION_REASONS",
    "RETRY_TABLE",
    "AttemptRecord",
    "AttemptRunner",
    "AuthBillingError",
    "FakeLLM",
    "FakeScriptExhausted",
    "FinalAnswer",
    "FunctionCall",
    "LLMClient",
    "LLMRequest",
    "LLMResponse",
    "Message",
    "ModelTurn",
    "ProviderError",
    "ToolMode",
    "ToolResult",
    "Usage",
    "UserMessage",
    "final_answer_json_schema",
    "make_llm_client",
]
