import dataclasses
import hashlib
import re

import pytest

from support_agent.config import (
    GEMINI_MIN_TIMEOUT_S,
    GROQ_KNOWN_COMPATIBLE_MODELS,
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
        ("LLM_PROVIDER", "grok"),
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


# --- provider-aware settings: GroqCloud (P-008) ----------------------------------------------

GROQ_KEY = "groq-unit-test-dummy-key-0123"


def groq_env(**extra: str) -> dict[str, str]:
    return {"LLM_PROVIDER": "groq", "GROQ_API_KEY": GROQ_KEY, **extra}


def test_groq_defaults():
    s = Settings.from_env(groq_env())
    assert s.provider == "groq"
    assert s.primary_model == "openai/gpt-oss-120b"
    assert s.fallback_model == "openai/gpt-oss-20b"
    assert s.reasoning_effort == "low"
    assert s.tpm_budget == 8000
    assert s.min_call_interval_s == 0.0
    assert s.max_output_tokens == 1024  # reasoning tokens count toward max_completion_tokens
    assert s.credential_env_var == "GROQ_API_KEY"
    assert s.credential_fingerprint() == credential_fingerprint(GROQ_KEY)


def test_groq_known_compatible_set():
    assert {"openai/gpt-oss-120b", "openai/gpt-oss-20b"} == GROQ_KNOWN_COMPATIBLE_MODELS


def test_groq_reads_only_groq_api_key():
    s = Settings.from_env(
        groq_env(GOOGLE_API_KEY=FAKE_KEY, GEMINI_API_KEY=INHERITED_KEY),
    )
    assert s.api_key is not None
    assert s.api_key.reveal() == GROQ_KEY
    assert s.credential_fingerprint() == credential_fingerprint(GROQ_KEY)


@pytest.mark.parametrize("other", ["GOOGLE_API_KEY", "GEMINI_API_KEY"])
def test_groq_never_falls_back_to_google_or_gemini_keys(other):
    with pytest.raises(ConfigError, match="GROQ_API_KEY is not set"):
        Settings.from_env({"LLM_PROVIDER": "groq", other: FAKE_KEY})


def test_gemini_ignores_groq_api_key():
    with pytest.raises(ConfigError, match="GOOGLE_API_KEY is not set"):
        Settings.from_env({"LLM_PROVIDER": "gemini", "GROQ_API_KEY": GROQ_KEY})
    s = Settings.from_env(gemini_env(GROQ_API_KEY=GROQ_KEY))
    assert s.api_key is not None and s.api_key.reveal() == FAKE_KEY
    assert s.credential_env_var == "GOOGLE_API_KEY"


def test_fake_provider_ignores_groq_api_key():
    s = Settings.from_env({"LLM_PROVIDER": "fake", "GROQ_API_KEY": GROQ_KEY})
    assert s.api_key is None and s.credential_env_var == "GOOGLE_API_KEY"


def test_groq_repr_hides_key():
    s = Settings.from_env(groq_env())
    for text in (repr(s), str(s), repr(s.api_key), str(dataclasses.asdict(s))):
        assert GROQ_KEY not in text


def test_groq_models_overridable_and_gemini_vars_ignored():
    s = Settings.from_env(
        groq_env(
            GROQ_PRIMARY_MODEL="openai/gpt-oss-20b",
            GROQ_FALLBACK_MODEL="openai/gpt-oss-120b",
            GEMINI_PRIMARY_MODEL="not-a-groq-model",
        )
    )
    assert (s.primary_model, s.fallback_model) == ("openai/gpt-oss-20b", "openai/gpt-oss-120b")


def test_gemini_ignores_groq_model_vars():
    s = Settings.from_env(gemini_env(GROQ_PRIMARY_MODEL="openai/gpt-oss-20b"))
    assert s.primary_model == "gemini-3.5-flash-lite"


@pytest.mark.parametrize("var", ["GROQ_PRIMARY_MODEL", "GROQ_FALLBACK_MODEL"])
def test_groq_unverified_model_needs_override(var):
    with pytest.raises(ConfigError, match="known-compatible"):
        Settings.from_env(groq_env(**{var: "qwen/qwen3.8-27b"}))
    s = Settings.from_env(groq_env(**{var: "qwen/qwen3.8-27b"}), allow_unverified_model=True)
    assert "qwen/qwen3.8-27b" in (s.primary_model, s.fallback_model)


def test_groq_gemini_models_are_not_groq_compatible():
    with pytest.raises(ConfigError, match="GROQ_PRIMARY_MODEL"):
        Settings.from_env(groq_env(GROQ_PRIMARY_MODEL="gemini-3.5-flash-lite"))


def test_groq_empty_fallback_disables_it_and_equal_fallback_warns():
    assert Settings.from_env(groq_env(GROQ_FALLBACK_MODEL="")).fallback_model is None
    s = Settings.from_env(groq_env(GROQ_FALLBACK_MODEL="openai/gpt-oss-120b", CASE_DEADLINE_S="90"))
    assert s.fallback_model is None
    assert s.warnings == (
        "GROQ_FALLBACK_MODEL equals GROQ_PRIMARY_MODEL (openai/gpt-oss-120b); fallback ignored",
    )


def test_groq_timeout_is_not_clamped_to_the_gemini_minimum():
    s = Settings.from_env(groq_env(LLM_TIMEOUT_S="4", CASE_DEADLINE_S="90"))
    assert (s.timeout_s, s.warnings) == (4.0, ())


def test_groq_overrides():
    s = Settings.from_env(
        groq_env(
            GROQ_REASONING_EFFORT="MEDIUM",
            GROQ_TPM_BUDGET="6000",
            GROQ_MIN_CALL_INTERVAL_S="2.5",
            LLM_MAX_OUTPUT_TOKENS="800",
        )
    )
    assert (s.reasoning_effort, s.tpm_budget, s.min_call_interval_s) == ("medium", 6000, 2.5)
    assert s.max_output_tokens == 800


def test_groq_pacing_can_be_disabled():
    s = Settings.from_env(groq_env(GROQ_TPM_BUDGET="0", GROQ_MIN_CALL_INTERVAL_S="0"))
    assert (s.tpm_budget, s.min_call_interval_s, s.warnings) == (0, 0.0, ())


def test_groq_paced_case_deadline_defaults_to_180_without_warning():
    s = Settings.from_env(groq_env())
    assert (s.tpm_budget, s.case_deadline_s, s.warnings) == (8000, 180.0, ())
    # Empty means unset, like every other variable.
    assert Settings.from_env(groq_env(CASE_DEADLINE_S="")).case_deadline_s == 180.0
    # Min-interval pacing alone also counts as paced.
    s = Settings.from_env(groq_env(GROQ_TPM_BUDGET="0", GROQ_MIN_CALL_INTERVAL_S="2"))
    assert (s.case_deadline_s, s.warnings) == (180.0, ())


def test_groq_unpaced_case_deadline_keeps_the_general_default():
    s = Settings.from_env(groq_env(GROQ_TPM_BUDGET="0"))
    assert (s.case_deadline_s, s.warnings) == (30.0, ())


def test_non_groq_providers_keep_the_general_case_deadline_default():
    assert Settings.from_env(gemini_env()).case_deadline_s == 30.0
    assert Settings.from_env({"LLM_PROVIDER": "fake"}).case_deadline_s == 30.0


@pytest.mark.parametrize("deadline", ["30", "69.9"])
def test_groq_explicit_case_deadline_below_a_pacing_window_plus_an_attempt_warns(deadline):
    s = Settings.from_env(groq_env(CASE_DEADLINE_S=deadline))
    assert s.case_deadline_s == float(deadline)  # kept: a warning, not an error
    assert len(s.warnings) == 1
    warning = s.warnings[0]
    assert f"CASE_DEADLINE_S={float(deadline):g}" in warning
    assert "pacing wait (60 s)" in warning and "LLM_TIMEOUT_S=10" in warning
    assert "without being sent" in warning


def test_groq_explicit_case_deadline_covering_a_window_and_an_attempt_is_quiet():
    assert Settings.from_env(groq_env(CASE_DEADLINE_S="70")).warnings == ()
    s = Settings.from_env(groq_env(CASE_DEADLINE_S="70", LLM_TIMEOUT_S="15"))
    assert len(s.warnings) == 1 and "LLM_TIMEOUT_S=15" in s.warnings[0]
    s = Settings.from_env(groq_env(CASE_DEADLINE_S="5", GROQ_TPM_BUDGET="0"))
    assert s.case_deadline_s == 5.0 and len(s.warnings) == 1
    assert "below LLM_TIMEOUT_S" in s.warnings[0]  # only the general warning when unpaced


def test_groq_min_interval_only_pacing_warns_against_its_own_wait():
    env = groq_env(GROQ_TPM_BUDGET="0", GROQ_MIN_CALL_INTERVAL_S="20")
    assert Settings.from_env({**env, "CASE_DEADLINE_S": "30"}).warnings == ()
    (warning,) = Settings.from_env({**env, "CASE_DEADLINE_S": "25"}).warnings
    assert "pacing wait (20 s)" in warning


def test_gemini_default_output_tokens_unchanged_by_groq_default():
    assert Settings.from_env(gemini_env()).max_output_tokens == 600
    assert Settings.from_env({"LLM_PROVIDER": "fake"}).max_output_tokens == 600


@pytest.mark.parametrize(
    ("var", "value"),
    [
        ("GROQ_REASONING_EFFORT", "minimal"),
        ("GROQ_REASONING_EFFORT", "extreme"),
        ("GROQ_TPM_BUDGET", "-1"),
        ("GROQ_TPM_BUDGET", "lots"),
        ("GROQ_MIN_CALL_INTERVAL_S", "-0.5"),
        ("GROQ_MIN_CALL_INTERVAL_S", "inf"),
        ("GROQ_MIN_CALL_INTERVAL_S", "nan"),
    ],
)
def test_groq_invalid_values_raise_config_error(var, value):
    with pytest.raises(ConfigError, match=var):
        Settings.from_env(groq_env(**{var: value}))


# --- provider-scoped knobs (R-02 #4): an inactive provider's settings are never parsed ---------

INVALID_GROQ_KNOBS = {
    "GROQ_REASONING_EFFORT": "extreme",
    "GROQ_TPM_BUDGET": "not-a-number",
    "GROQ_MIN_CALL_INTERVAL_S": "-3",
}
INVALID_GEMINI_KNOBS = {"GEMINI_THINKING_LEVEL": "extreme"}


def test_gemini_ignores_invalid_groq_knobs():
    s = Settings.from_env(gemini_env(**INVALID_GROQ_KNOBS))
    assert (s.provider, s.api_key.reveal()) == ("gemini", FAKE_KEY)
    assert (s.reasoning_effort, s.tpm_budget, s.min_call_interval_s) == ("low", 8000, 0.0)
    assert (s.case_deadline_s, s.warnings) == (30.0, ())


def test_groq_ignores_invalid_gemini_knobs():
    s = Settings.from_env(groq_env(**INVALID_GEMINI_KNOBS))
    assert (s.provider, s.thinking_level, s.warnings) == ("groq", "minimal", ())


def test_fake_ignores_invalid_gemini_and_groq_knobs():
    s = Settings.from_env({"LLM_PROVIDER": "fake", **INVALID_GROQ_KNOBS, **INVALID_GEMINI_KNOBS})
    assert (s.thinking_level, s.reasoning_effort) == ("minimal", "low")
    assert (s.tpm_budget, s.min_call_interval_s, s.case_deadline_s) == (8000, 0.0, 30.0)
    assert s.warnings == ()


def test_active_provider_knobs_are_still_validated():
    with pytest.raises(ConfigError, match="GEMINI_THINKING_LEVEL"):
        Settings.from_env(gemini_env(**INVALID_GEMINI_KNOBS))
    for var, value in INVALID_GROQ_KNOBS.items():
        with pytest.raises(ConfigError, match=var):
            Settings.from_env(groq_env(**{var: value}))


def test_inactive_knobs_do_not_leak_into_the_active_settings():
    s = Settings.from_env(gemini_env(GROQ_REASONING_EFFORT="high", GROQ_TPM_BUDGET="100"))
    assert (s.reasoning_effort, s.tpm_budget) == ("low", 8000)
    s = Settings.from_env(groq_env(GEMINI_THINKING_LEVEL="high"))
    assert s.thinking_level == "minimal"
