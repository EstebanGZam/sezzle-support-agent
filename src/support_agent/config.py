"""Runtime settings read from the environment (architecture §8).

Each provider has exactly one key env var (AR-09, generalised): ``gemini`` reads only
``GOOGLE_API_KEY`` (an inherited ``GEMINI_API_KEY`` is never consulted) and ``groq`` reads only
``GROQ_API_KEY`` (never the Google/Gemini variables). The key is held in a ``Secret`` so it never
appears in ``repr``/``str``, logs, traces or ``dataclasses.asdict`` output (SEC-13); only its
fingerprint may be recorded.
"""

from __future__ import annotations

import hashlib
import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

CREDENTIAL_ENV_VAR = "GOOGLE_API_KEY"
GROQ_CREDENTIAL_ENV_VAR = "GROQ_API_KEY"
# The one key env var per provider; ``fake`` keeps the default provider's (the key is optional).
CREDENTIAL_ENV_VARS = {
    "gemini": CREDENTIAL_ENV_VAR,
    "groq": GROQ_CREDENTIAL_ENV_VAR,
    "fake": CREDENTIAL_ENV_VAR,
}
PROVIDERS = frozenset(CREDENTIAL_ENV_VARS)
# Verified to accept tools + JSON response schema in one call (smoke test S-001).
KNOWN_COMPATIBLE_MODELS = frozenset({"gemini-3.5-flash-lite", "gemini-3.1-flash-lite"})
# Production GroqCloud models with tool calling (the answer is a ``submit_answer`` tool call).
GROQ_KNOWN_COMPATIBLE_MODELS = frozenset({"openai/gpt-oss-120b", "openai/gpt-oss-20b"})
THINKING_LEVELS = frozenset({"minimal", "low", "medium", "high"})
REASONING_EFFORTS = frozenset({"low", "medium", "high"})

DEFAULT_PROVIDER = "gemini"
DEFAULT_PRIMARY_MODEL = "gemini-3.5-flash-lite"
DEFAULT_FALLBACK_MODEL = "gemini-3.1-flash-lite"
DEFAULT_THINKING_LEVEL = "minimal"
DEFAULT_GROQ_PRIMARY_MODEL = "openai/gpt-oss-120b"
DEFAULT_GROQ_FALLBACK_MODEL = "openai/gpt-oss-20b"
DEFAULT_REASONING_EFFORT = "low"
# GroqCloud free plan: 8K tokens per minute per model; 0 disables client-side TPM pacing.
DEFAULT_GROQ_TPM_BUDGET = 8000
DEFAULT_GROQ_MIN_CALL_INTERVAL_S = 0.0
# A TPM pacing wait can last up to a full minute and counts against the case deadline.
GROQ_PACING_WINDOW_S = 60.0
DEFAULT_TIMEOUT_S = 10.0
# The Gemini API rejects request deadlines below 10 s (HTTP 400 INVALID_ARGUMENT).
GEMINI_MIN_TIMEOUT_S = 10.0
# Primary → fallback → one optional same-model retry (architecture §7), deadline permitting.
DEFAULT_MAX_ATTEMPTS = 3
# One absolute wall-clock budget per case, shared by every semantic call and transport attempt
# (architecture §7 "case deadline"); ≥ 2x the Gemini minimum so a timeout can be retried once.
DEFAULT_CASE_DEADLINE_S = 30.0
# Groq with pacing on: a paced call may wait up to a full window before it is sent, and a case can
# make more than one semantic call (architecture §8 "Eval runs"), so the default deadline is wider.
DEFAULT_GROQ_PACED_CASE_DEADLINE_S = 180.0
DEFAULT_MAX_OUTPUT_TOKENS = 600
# gpt-oss counts reasoning tokens in ``max_completion_tokens``, so Groq needs more headroom.
DEFAULT_GROQ_MAX_OUTPUT_TOKENS = 1024
DEFAULT_INPUT_CHAR_CAP = 2000
DEFAULT_MAX_LLM_CALLS_PER_BATCH = 2000
DEFAULT_DATA_DIR = "data"


# Per-provider model variables: (primary var, fallback var, default primary, default fallback,
# known-compatible set). ``fake`` shares Gemini's so offline runs look like the default provider.
_MODEL_VARS: dict[str, tuple[str, str, str, str, frozenset[str]]] = {
    "gemini": (
        "GEMINI_PRIMARY_MODEL",
        "GEMINI_FALLBACK_MODEL",
        DEFAULT_PRIMARY_MODEL,
        DEFAULT_FALLBACK_MODEL,
        KNOWN_COMPATIBLE_MODELS,
    ),
    "groq": (
        "GROQ_PRIMARY_MODEL",
        "GROQ_FALLBACK_MODEL",
        DEFAULT_GROQ_PRIMARY_MODEL,
        DEFAULT_GROQ_FALLBACK_MODEL,
        GROQ_KNOWN_COMPATIBLE_MODELS,
    ),
}
_MODEL_VARS["fake"] = _MODEL_VARS["gemini"]


class ConfigError(Exception):
    """Unusable configuration; the CLI maps it to exit code 2."""


class Secret:
    """Opaque holder for a credential; never renders its value."""

    __slots__ = ("_value",)

    def __init__(self, value: str) -> None:
        self._value = value

    def reveal(self) -> str:
        return self._value

    def fingerprint(self) -> str:
        return credential_fingerprint(self._value)

    def __repr__(self) -> str:
        return "Secret('**********')"

    __str__ = __repr__

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Secret) and other._value == self._value

    def __hash__(self) -> int:
        return hash(self._value)


def credential_fingerprint(value: str) -> str:
    """First 12 hex chars of the SHA-256 of ``value``; safe to record, never the key."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]


@dataclass(frozen=True)
class Settings:
    provider: str = DEFAULT_PROVIDER
    primary_model: str = DEFAULT_PRIMARY_MODEL
    fallback_model: str | None = DEFAULT_FALLBACK_MODEL
    api_key: Secret | None = field(default=None, repr=False)
    thinking_level: str = DEFAULT_THINKING_LEVEL
    reasoning_effort: str = DEFAULT_REASONING_EFFORT
    tpm_budget: int = DEFAULT_GROQ_TPM_BUDGET
    min_call_interval_s: float = DEFAULT_GROQ_MIN_CALL_INTERVAL_S
    timeout_s: float = DEFAULT_TIMEOUT_S
    max_attempts: int = DEFAULT_MAX_ATTEMPTS
    case_deadline_s: float = DEFAULT_CASE_DEADLINE_S
    max_output_tokens: int = DEFAULT_MAX_OUTPUT_TOKENS
    input_char_cap: int = DEFAULT_INPUT_CHAR_CAP
    max_llm_calls_per_batch: int = DEFAULT_MAX_LLM_CALLS_PER_BATCH
    data_dir: Path = PROJECT_ROOT / DEFAULT_DATA_DIR
    fake_llm_script: Path | None = None
    allow_unverified_model: bool = False
    warnings: tuple[str, ...] = ()

    @property
    def policies_dir(self) -> Path:
        return self.data_dir / "policies"

    @property
    def orders_path(self) -> Path:
        return self.data_dir / "orders.json"

    @property
    def credential_env_var(self) -> str:
        """The single env var the active provider's key is read from."""
        return CREDENTIAL_ENV_VARS.get(self.provider, CREDENTIAL_ENV_VAR)

    def credential_fingerprint(self) -> str | None:
        """Fingerprint of the configured key, or ``None`` when no key is set."""
        return self.api_key.fingerprint() if self.api_key else None

    @classmethod
    def from_env(
        cls,
        environ: Mapping[str, str] | None = None,
        *,
        allow_unverified_model: bool = False,
    ) -> Settings:
        """Build settings from ``environ`` (default ``os.environ``).

        ``allow_unverified_model`` is the explicit override (CLI ``--allow-unverified-model``)
        for model IDs outside the provider's known-compatible set (``KNOWN_COMPATIBLE_MODELS``
        for Gemini, ``GROQ_KNOWN_COMPATIBLE_MODELS`` for Groq).
        Raises ``ConfigError`` on any invalid or missing value.
        """
        env = os.environ if environ is None else environ
        warnings: list[str] = []

        provider = _get(env, "LLM_PROVIDER", DEFAULT_PROVIDER).lower()
        if provider not in PROVIDERS:
            raise ConfigError(f"LLM_PROVIDER must be one of {sorted(PROVIDERS)}, got {provider!r}")

        primary_var, fallback_var, default_primary, default_fallback, known = _MODEL_VARS[provider]
        primary = _get(env, primary_var, default_primary)
        _check_model(primary_var, primary, known, allow_unverified_model)

        # Unset -> default; set but empty -> fallback disabled.
        fallback: str | None = env.get(fallback_var, default_fallback).strip()
        if not fallback:
            fallback = None
        elif fallback == primary:
            warnings.append(f"{fallback_var} equals {primary_var} ({primary}); fallback ignored")
            fallback = None
        else:
            _check_model(fallback_var, fallback, known, allow_unverified_model)

        # Exactly one key variable per provider; every other key variable is ignored.
        key_var = CREDENTIAL_ENV_VARS[provider]
        raw_key = env.get(key_var, "").strip()
        api_key = Secret(raw_key) if raw_key else None
        if api_key is None and provider != "fake":
            ignored = (
                "GEMINI_API_KEY is deliberately ignored"
                if provider == "gemini"
                else "GOOGLE_API_KEY and GEMINI_API_KEY are deliberately ignored"
            )
            raise ConfigError(
                f"{key_var} is not set; it is required when LLM_PROVIDER={provider} "
                f"({ignored}). Set it in .env or use LLM_PROVIDER=fake for offline runs."
            )

        # Provider-specific knobs are read only for the active provider; an inactive provider's
        # variables are never parsed (a stale value cannot block startup) and keep inert defaults.
        thinking_level = DEFAULT_THINKING_LEVEL
        if provider == "gemini":
            thinking_level = _get(env, "GEMINI_THINKING_LEVEL", DEFAULT_THINKING_LEVEL).lower()
            if thinking_level not in THINKING_LEVELS:
                raise ConfigError(
                    f"GEMINI_THINKING_LEVEL must be one of {sorted(THINKING_LEVELS)}, "
                    f"got {thinking_level!r}"
                )

        reasoning_effort = DEFAULT_REASONING_EFFORT
        tpm_budget = DEFAULT_GROQ_TPM_BUDGET
        min_call_interval_s = DEFAULT_GROQ_MIN_CALL_INTERVAL_S
        if provider == "groq":
            reasoning_effort = _get(env, "GROQ_REASONING_EFFORT", DEFAULT_REASONING_EFFORT).lower()
            if reasoning_effort not in REASONING_EFFORTS:
                raise ConfigError(
                    f"GROQ_REASONING_EFFORT must be one of {sorted(REASONING_EFFORTS)}, "
                    f"got {reasoning_effort!r}"
                )
            tpm_budget = _non_negative_int(env, "GROQ_TPM_BUDGET", DEFAULT_GROQ_TPM_BUDGET)
            min_call_interval_s = _non_negative_float(
                env, "GROQ_MIN_CALL_INTERVAL_S", DEFAULT_GROQ_MIN_CALL_INTERVAL_S
            )

        timeout_s = _positive_float(env, "LLM_TIMEOUT_S", DEFAULT_TIMEOUT_S)
        if provider == "gemini" and timeout_s < GEMINI_MIN_TIMEOUT_S:
            warnings.append(
                f"LLM_TIMEOUT_S={timeout_s:g} is below the Gemini minimum request deadline; "
                f"raised to {GEMINI_MIN_TIMEOUT_S:g}"
            )
            timeout_s = GEMINI_MIN_TIMEOUT_S

        # Longest client-side pacing wait before a Groq call: a full TPM window, or the minimum
        # interval between calls (0 when pacing is off or the provider is not Groq).
        max_pacing_wait_s = 0.0
        if provider == "groq":
            max_pacing_wait_s = max(
                GROQ_PACING_WINDOW_S if tpm_budget > 0 else 0.0, min_call_interval_s
            )
        default_deadline_s = (
            DEFAULT_GROQ_PACED_CASE_DEADLINE_S if max_pacing_wait_s > 0 else DEFAULT_CASE_DEADLINE_S
        )
        case_deadline_s = _positive_float(env, "CASE_DEADLINE_S", default_deadline_s)
        if case_deadline_s < timeout_s:
            warnings.append(
                f"CASE_DEADLINE_S={case_deadline_s:g} is below LLM_TIMEOUT_S={timeout_s:g}; "
                f"every attempt is capped by the case deadline"
            )
        if max_pacing_wait_s > 0 and case_deadline_s < max_pacing_wait_s + timeout_s:
            warnings.append(
                f"CASE_DEADLINE_S={case_deadline_s:g} is below one Groq pacing wait "
                f"({max_pacing_wait_s:g} s) plus one attempt (LLM_TIMEOUT_S={timeout_s:g}); "
                f"a paced call that cannot start before the case deadline fails as "
                f"rate_limit_minute without being sent. Unset CASE_DEADLINE_S (default "
                f"{DEFAULT_GROQ_PACED_CASE_DEADLINE_S:g} s for paced Groq runs) or raise it"
            )

        fake_script = _get(env, "FAKE_LLM_SCRIPT", "")
        data_dir = Path(_get(env, "DATA_DIR", DEFAULT_DATA_DIR))
        if not data_dir.is_absolute():
            data_dir = PROJECT_ROOT / data_dir

        return cls(
            provider=provider,
            primary_model=primary,
            fallback_model=fallback,
            api_key=api_key,
            thinking_level=thinking_level,
            reasoning_effort=reasoning_effort,
            tpm_budget=tpm_budget,
            min_call_interval_s=min_call_interval_s,
            timeout_s=timeout_s,
            max_attempts=_positive_int(env, "LLM_MAX_ATTEMPTS", DEFAULT_MAX_ATTEMPTS),
            case_deadline_s=case_deadline_s,
            max_output_tokens=_positive_int(
                env,
                "LLM_MAX_OUTPUT_TOKENS",
                DEFAULT_GROQ_MAX_OUTPUT_TOKENS if provider == "groq" else DEFAULT_MAX_OUTPUT_TOKENS,
            ),
            input_char_cap=_positive_int(env, "INPUT_CHAR_CAP", DEFAULT_INPUT_CHAR_CAP),
            max_llm_calls_per_batch=_positive_int(
                env, "MAX_LLM_CALLS_PER_BATCH", DEFAULT_MAX_LLM_CALLS_PER_BATCH
            ),
            data_dir=data_dir,
            fake_llm_script=Path(fake_script) if provider == "fake" and fake_script else None,
            allow_unverified_model=allow_unverified_model,
            warnings=tuple(warnings),
        )


def _get(env: Mapping[str, str], name: str, default: str) -> str:
    """Env value stripped; empty or unset falls back to ``default``."""
    value = env.get(name, "").strip()
    return value or default


def _check_model(var: str, model_id: str, known: frozenset[str], allow_unverified: bool) -> None:
    if model_id.endswith("-latest"):
        raise ConfigError(f"{var} must be an explicit pinned model ID, not an alias: {model_id!r}")
    if model_id not in known and not allow_unverified:
        raise ConfigError(
            f"{var}={model_id!r} is not in the known-compatible set "
            f"{sorted(known)} (tools + structured answer); "
            f"pass --allow-unverified-model to override"
        )


def _positive_int(env: Mapping[str, str], name: str, default: int) -> int:
    raw = _get(env, name, str(default))
    try:
        value = int(raw)
    except ValueError:
        raise ConfigError(f"{name} must be an integer, got {raw!r}") from None
    if value <= 0:
        raise ConfigError(f"{name} must be > 0, got {value}")
    return value


def _positive_float(env: Mapping[str, str], name: str, default: float) -> float:
    raw = _get(env, name, str(default))
    try:
        value = float(raw)
    except ValueError:
        raise ConfigError(f"{name} must be a number, got {raw!r}") from None
    if not value > 0 or value == float("inf"):
        raise ConfigError(f"{name} must be a finite number > 0, got {raw!r}")
    return value


def _non_negative_int(env: Mapping[str, str], name: str, default: int) -> int:
    raw = _get(env, name, str(default))
    try:
        value = int(raw)
    except ValueError:
        raise ConfigError(f"{name} must be an integer, got {raw!r}") from None
    if value < 0:
        raise ConfigError(f"{name} must be >= 0, got {value}")
    return value


def _non_negative_float(env: Mapping[str, str], name: str, default: float) -> float:
    raw = _get(env, name, str(default))
    try:
        value = float(raw)
    except ValueError:
        raise ConfigError(f"{name} must be a number, got {raw!r}") from None
    if not value >= 0 or value == float("inf"):
        raise ConfigError(f"{name} must be a finite number >= 0, got {raw!r}")
    return value
