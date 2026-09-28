"""Runtime settings read from the environment (architecture §8).

The API key is read only from ``GOOGLE_API_KEY`` (AR-09); an inherited ``GEMINI_API_KEY`` is
never consulted. The key is held in a ``Secret`` so it never appears in ``repr``/``str``, logs,
traces or ``dataclasses.asdict`` output (SEC-13); only its fingerprint may be recorded.
"""

from __future__ import annotations

import hashlib
import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

CREDENTIAL_ENV_VAR = "GOOGLE_API_KEY"
PROVIDERS = frozenset({"gemini", "fake"})
# Verified to accept tools + JSON response schema in one call (smoke test S-001).
KNOWN_COMPATIBLE_MODELS = frozenset({"gemini-3.5-flash-lite", "gemini-3.1-flash-lite"})
THINKING_LEVELS = frozenset({"minimal", "low", "medium", "high"})

DEFAULT_PROVIDER = "gemini"
DEFAULT_PRIMARY_MODEL = "gemini-3.5-flash-lite"
DEFAULT_FALLBACK_MODEL = "gemini-3.1-flash-lite"
DEFAULT_THINKING_LEVEL = "minimal"
DEFAULT_TIMEOUT_S = 10.0
# The Gemini API rejects request deadlines below 10 s (HTTP 400 INVALID_ARGUMENT).
GEMINI_MIN_TIMEOUT_S = 10.0
DEFAULT_MAX_ATTEMPTS = 2
DEFAULT_MAX_OUTPUT_TOKENS = 600
DEFAULT_INPUT_CHAR_CAP = 2000
DEFAULT_MAX_LLM_CALLS_PER_BATCH = 2000
DEFAULT_DATA_DIR = "data"


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
    timeout_s: float = DEFAULT_TIMEOUT_S
    max_attempts: int = DEFAULT_MAX_ATTEMPTS
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
        return CREDENTIAL_ENV_VAR

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
        for model IDs outside ``KNOWN_COMPATIBLE_MODELS``.
        Raises ``ConfigError`` on any invalid or missing value.
        """
        env = os.environ if environ is None else environ
        warnings: list[str] = []

        provider = _get(env, "LLM_PROVIDER", DEFAULT_PROVIDER).lower()
        if provider not in PROVIDERS:
            raise ConfigError(f"LLM_PROVIDER must be one of {sorted(PROVIDERS)}, got {provider!r}")

        primary = _get(env, "GEMINI_PRIMARY_MODEL", DEFAULT_PRIMARY_MODEL)
        _check_model("GEMINI_PRIMARY_MODEL", primary, allow_unverified_model)

        # Unset -> default; set but empty -> fallback disabled.
        fallback: str | None = env.get("GEMINI_FALLBACK_MODEL", DEFAULT_FALLBACK_MODEL).strip()
        if not fallback:
            fallback = None
        elif fallback == primary:
            warnings.append(
                f"GEMINI_FALLBACK_MODEL equals GEMINI_PRIMARY_MODEL ({primary}); fallback ignored"
            )
            fallback = None
        else:
            _check_model("GEMINI_FALLBACK_MODEL", fallback, allow_unverified_model)

        raw_key = env.get(CREDENTIAL_ENV_VAR, "").strip()
        api_key = Secret(raw_key) if raw_key else None
        if provider == "gemini" and api_key is None:
            raise ConfigError(
                f"{CREDENTIAL_ENV_VAR} is not set; it is required when LLM_PROVIDER=gemini "
                f"(GEMINI_API_KEY is deliberately ignored). Set it in .env or use "
                f"LLM_PROVIDER=fake for offline runs."
            )

        thinking_level = _get(env, "GEMINI_THINKING_LEVEL", DEFAULT_THINKING_LEVEL).lower()
        if thinking_level not in THINKING_LEVELS:
            raise ConfigError(
                f"GEMINI_THINKING_LEVEL must be one of {sorted(THINKING_LEVELS)}, "
                f"got {thinking_level!r}"
            )

        timeout_s = _positive_float(env, "LLM_TIMEOUT_S", DEFAULT_TIMEOUT_S)
        if provider == "gemini" and timeout_s < GEMINI_MIN_TIMEOUT_S:
            warnings.append(
                f"LLM_TIMEOUT_S={timeout_s:g} is below the Gemini minimum request deadline; "
                f"raised to {GEMINI_MIN_TIMEOUT_S:g}"
            )
            timeout_s = GEMINI_MIN_TIMEOUT_S

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
            timeout_s=timeout_s,
            max_attempts=_positive_int(env, "LLM_MAX_ATTEMPTS", DEFAULT_MAX_ATTEMPTS),
            max_output_tokens=_positive_int(
                env, "LLM_MAX_OUTPUT_TOKENS", DEFAULT_MAX_OUTPUT_TOKENS
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


def _check_model(var: str, model_id: str, allow_unverified: bool) -> None:
    if model_id.endswith("-latest"):
        raise ConfigError(f"{var} must be an explicit pinned model ID, not an alias: {model_id!r}")
    if model_id not in KNOWN_COMPATIBLE_MODELS and not allow_unverified:
        raise ConfigError(
            f"{var}={model_id!r} is not in the known-compatible set "
            f"{sorted(KNOWN_COMPATIBLE_MODELS)} (tools + JSON schema in one call); "
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
