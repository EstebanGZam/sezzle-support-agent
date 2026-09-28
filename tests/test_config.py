import dataclasses
import hashlib
import re

import pytest

from support_agent.config import (
    GEMINI_MIN_TIMEOUT_S,
    KNOWN_COMPATIBLE_MODELS,
    PROJECT_ROOT,
    ConfigError,
    Settings,
    credential_fingerprint,
)

FAKE_KEY = "unit-test-dummy-key-0123456789"
INHERITED_KEY = "inherited-dummy-key-9876543210"


def gemini_env(**extra: str) -> dict[str, str]:
    return {"LLM_PROVIDER": "gemini", "GOOGLE_API_KEY": FAKE_KEY, **extra}


def test_defaults_match_architecture():
    s = Settings.from_env(gemini_env())
    assert s.provider == "gemini"
    assert s.primary_model == "gemini-3.5-flash-lite"
    assert s.fallback_model == "gemini-3.1-flash-lite"
    assert s.thinking_level == "minimal"
    assert s.timeout_s == 10.0
    assert s.max_attempts == 3
    assert s.case_deadline_s == 30.0
    assert s.max_output_tokens == 600
    assert s.input_char_cap == 2000
    assert s.max_llm_calls_per_batch == 2000
    assert s.data_dir == PROJECT_ROOT / "data"
    assert s.policies_dir == PROJECT_ROOT / "data" / "policies"
    assert s.orders_path == PROJECT_ROOT / "data" / "orders.json"
    assert s.fake_llm_script is None
    assert s.warnings == ()


def test_provider_defaults_to_gemini_when_unset():
    s = Settings.from_env({"GOOGLE_API_KEY": FAKE_KEY})
    assert s.provider == "gemini"


def test_default_data_dir_points_at_repo_data():
    assert (Settings.from_env({"LLM_PROVIDER": "fake"}).orders_path).is_file()


def test_settings_are_frozen():
    s = Settings.from_env({"LLM_PROVIDER": "fake"})
    with pytest.raises(dataclasses.FrozenInstanceError):
        s.primary_model = "other"  # type: ignore[misc]


def test_models_overridable_by_env():
    s = Settings.from_env(
        gemini_env(
            GEMINI_PRIMARY_MODEL="gemini-3.1-flash-lite",
            GEMINI_FALLBACK_MODEL="gemini-3.5-flash-lite",
        )
    )
    assert s.primary_model == "gemini-3.1-flash-lite"
    assert s.fallback_model == "gemini-3.5-flash-lite"


def test_numeric_overrides():
    s = Settings.from_env(
        gemini_env(
            LLM_TIMEOUT_S="12.5",
            LLM_MAX_ATTEMPTS="3",
            LLM_MAX_OUTPUT_TOKENS="800",
            INPUT_CHAR_CAP="1000",
            MAX_LLM_CALLS_PER_BATCH="10",
            GEMINI_THINKING_LEVEL="LOW",
            CASE_DEADLINE_S="45",
        )
    )
    assert s.case_deadline_s == 45.0
    assert (s.timeout_s, s.max_attempts, s.max_output_tokens) == (12.5, 3, 800)
    assert (s.input_char_cap, s.max_llm_calls_per_batch, s.thinking_level) == (1000, 10, "low")


@pytest.mark.parametrize(
    ("var", "value"),
    [
        ("LLM_TIMEOUT_S", "abc"),
        ("LLM_TIMEOUT_S", "0"),
        ("LLM_TIMEOUT_S", "nan"),
        ("LLM_MAX_ATTEMPTS", "0"),
        ("LLM_MAX_ATTEMPTS", "1.5"),
        ("LLM_MAX_OUTPUT_TOKENS", "-1"),
        ("INPUT_CHAR_CAP", "x"),
        ("MAX_LLM_CALLS_PER_BATCH", "0"),
        ("CASE_DEADLINE_S", "0"),
        ("CASE_DEADLINE_S", "inf"),
        ("CASE_DEADLINE_S", "soon"),
        ("GEMINI_THINKING_LEVEL", "extreme"),
        ("LLM_PROVIDER", "openai"),
    ],
)
def test_invalid_values_raise_config_error(var, value):
    with pytest.raises(ConfigError, match=var):
        Settings.from_env(gemini_env(**{var: value}))


@pytest.mark.parametrize("value", ["8", "2.5", "9.99"])
def test_gemini_timeout_below_minimum_is_raised_with_warning(value):
    s = Settings.from_env(gemini_env(LLM_TIMEOUT_S=value))
    assert s.timeout_s == GEMINI_MIN_TIMEOUT_S == 10.0
    assert len(s.warnings) == 1
    assert "LLM_TIMEOUT_S" in s.warnings[0] and "raised to 10" in s.warnings[0]


def test_gemini_timeout_at_or_above_minimum_is_kept_without_warning():
    assert Settings.from_env(gemini_env(LLM_TIMEOUT_S="10")).timeout_s == 10.0
    s = Settings.from_env(gemini_env(LLM_TIMEOUT_S="15"))
    assert (s.timeout_s, s.warnings) == (15.0, ())


def test_default_case_deadline_allows_a_retry_at_the_gemini_minimum():
    assert Settings.from_env(gemini_env()).case_deadline_s >= 2 * GEMINI_MIN_TIMEOUT_S


def test_case_deadline_below_timeout_warns():
    s = Settings.from_env(gemini_env(CASE_DEADLINE_S="5"))
    assert s.case_deadline_s == 5.0
    assert len(s.warnings) == 1 and "CASE_DEADLINE_S" in s.warnings[0]


def test_fake_provider_timeout_is_not_clamped():
    s = Settings.from_env({"LLM_PROVIDER": "fake", "LLM_TIMEOUT_S": "2.5"})
    assert (s.timeout_s, s.warnings) == (2.5, ())


def test_empty_values_fall_back_to_defaults():
    s = Settings.from_env(gemini_env(LLM_TIMEOUT_S="", GEMINI_PRIMARY_MODEL=" "))
    assert s.timeout_s == 10.0
    assert s.primary_model == "gemini-3.5-flash-lite"


@pytest.mark.parametrize("var", ["GEMINI_PRIMARY_MODEL", "GEMINI_FALLBACK_MODEL"])
def test_incompatible_model_without_override_raises(var):
    with pytest.raises(ConfigError, match="known-compatible"):
        Settings.from_env(gemini_env(**{var: "gemini-2.5-flash-lite"}))


def test_incompatible_model_with_explicit_override_is_accepted():
    s = Settings.from_env(
        gemini_env(GEMINI_PRIMARY_MODEL="gemini-9.9-flash-lite"), allow_unverified_model=True
    )
    assert s.primary_model == "gemini-9.9-flash-lite"
    assert s.allow_unverified_model is True


def test_latest_alias_rejected_even_with_override():
    with pytest.raises(ConfigError, match="pinned"):
        Settings.from_env(
            gemini_env(GEMINI_PRIMARY_MODEL="gemini-flash-lite-latest"),
            allow_unverified_model=True,
        )


def test_known_compatible_set():
    assert {"gemini-3.5-flash-lite", "gemini-3.1-flash-lite"} == KNOWN_COMPATIBLE_MODELS


def test_empty_fallback_disables_it():
    assert Settings.from_env(gemini_env(GEMINI_FALLBACK_MODEL="")).fallback_model is None


def test_fallback_equal_to_primary_is_ignored_with_warning():
    s = Settings.from_env(gemini_env(GEMINI_FALLBACK_MODEL="gemini-3.5-flash-lite"))
    assert s.fallback_model is None
    assert len(s.warnings) == 1
    assert "fallback ignored" in s.warnings[0]


def test_missing_key_with_gemini_raises_clear_error():
    with pytest.raises(ConfigError, match="GOOGLE_API_KEY is not set"):
        Settings.from_env({"LLM_PROVIDER": "gemini"})


def test_blank_key_with_gemini_raises():
    with pytest.raises(ConfigError, match="GOOGLE_API_KEY"):
        Settings.from_env({"LLM_PROVIDER": "gemini", "GOOGLE_API_KEY": "  "})


def test_inherited_gemini_api_key_is_ignored_when_google_key_missing():
    with pytest.raises(ConfigError, match="GOOGLE_API_KEY"):
        Settings.from_env({"LLM_PROVIDER": "gemini", "GEMINI_API_KEY": INHERITED_KEY})


def test_inherited_gemini_api_key_is_never_used():
    s = Settings.from_env(gemini_env(GEMINI_API_KEY=INHERITED_KEY))
    assert s.api_key is not None
    assert s.api_key.reveal() == FAKE_KEY
    assert s.credential_fingerprint() == credential_fingerprint(FAKE_KEY)
    assert s.credential_fingerprint() != credential_fingerprint(INHERITED_KEY)


def test_from_env_reads_process_environment_but_ignores_gemini_api_key(monkeypatch):
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.setenv("GEMINI_API_KEY", INHERITED_KEY)
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    with pytest.raises(ConfigError, match="GOOGLE_API_KEY"):
        Settings.from_env()


def test_fake_provider_requires_no_key():
    s = Settings.from_env({"LLM_PROVIDER": "fake"})
    assert s.provider == "fake"
    assert s.api_key is None
    assert s.credential_fingerprint() is None


def test_fake_llm_script_only_for_fake_provider():
    assert (
        Settings.from_env({"LLM_PROVIDER": "fake", "FAKE_LLM_SCRIPT": "s.json"}).fake_llm_script
        is not None
    )
    assert Settings.from_env(gemini_env(FAKE_LLM_SCRIPT="s.json")).fake_llm_script is None


def test_credential_fingerprint_is_12_hex_sha256_prefix():
    s = Settings.from_env(gemini_env())
    fp = s.credential_fingerprint()
    assert fp is not None
    assert re.fullmatch(r"[0-9a-f]{12}", fp)
    assert fp == hashlib.sha256(FAKE_KEY.encode()).hexdigest()[:12]
    assert s.credential_env_var == "GOOGLE_API_KEY"


def test_repr_and_str_never_show_key():
    s = Settings.from_env(gemini_env())
    for text in (repr(s), str(s), repr(s.api_key), str(s.api_key), str(dataclasses.asdict(s))):
        assert FAKE_KEY not in text


def test_relative_data_dir_resolves_against_project_root(tmp_path):
    assert Settings.from_env(gemini_env(DATA_DIR="data")).data_dir == PROJECT_ROOT / "data"
    assert Settings.from_env(gemini_env(DATA_DIR=str(tmp_path))).data_dir == tmp_path
