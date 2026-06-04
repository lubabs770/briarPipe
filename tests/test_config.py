import textwrap

import pytest

from briarpipe.config import Config, ConfigError, load_config


def _write(tmp_path, body):
    p = tmp_path / "config.yml"
    p.write_text(textwrap.dedent(body), encoding="utf-8")
    return p


def test_minimal_config_applies_defaults(tmp_path):
    cfg = load_config(_write(tmp_path, "interests: AI and gardening\n"))
    assert isinstance(cfg, Config)
    assert cfg.interests == "AI and gardening"
    assert cfg.frequency == "weekly"
    assert cfg.token_budget.max_per_run == 120_000
    assert cfg.token_budget.cultivation_fraction == 0.2
    assert cfg.provider.name == "openai-compatible"
    assert cfg.provider.api_key_env == "LLM_API_KEY"
    assert cfg.delivery.gateway == "markdown"


def test_full_config_round_trips_values(tmp_path):
    cfg = load_config(
        _write(
            tmp_path,
            """
            interests: rockets
            frequency: Daily
            edition_name: Booster Weekly
            token_budget:
              max_per_run: 50000
              cultivation_fraction: 0.25
            bootstrap_sources:
              - https://a.example
              - https://b.example
            provider:
              name: OpenAI-Compatible
              base_url: https://openrouter.ai/api/v1
              model: meta-llama/llama-3.1-70b-instruct
              api_key_env: OPENROUTER_API_KEY
            delivery:
              gateway: email
              to: me@example.com
              smtp_host: smtp.example.com
            output:
              max_stories: 5
              sections: [Top, Misc]
              summary_length: short
            style: punchy
            """,
        )
    )
    assert cfg.frequency == "daily"  # normalized lowercase
    assert cfg.provider.name == "openai-compatible"  # normalized lowercase
    assert cfg.provider.base_url == "https://openrouter.ai/api/v1"
    assert cfg.provider.model == "meta-llama/llama-3.1-70b-instruct"
    assert cfg.provider.api_key_env == "OPENROUTER_API_KEY"
    assert cfg.token_budget.cultivation_budget == 12_500
    assert cfg.token_budget.curation_budget == 37_500
    assert cfg.bootstrap_sources == ["https://a.example", "https://b.example"]
    assert cfg.delivery.to == "me@example.com"
    assert cfg.delivery.options["smtp_host"] == "smtp.example.com"
    assert cfg.output.sections == ["Top", "Misc"]
    assert cfg.style == "punchy"


def test_missing_interests_rejected(tmp_path):
    with pytest.raises(ConfigError, match="interests"):
        load_config(_write(tmp_path, "frequency: weekly\n"))


def test_bad_frequency_rejected(tmp_path):
    with pytest.raises(ConfigError, match="frequency"):
        load_config(_write(tmp_path, "interests: x\nfrequency: hourly\n"))


def test_cultivation_fraction_out_of_range_rejected(tmp_path):
    with pytest.raises(ConfigError, match="cultivation_fraction"):
        load_config(
            _write(
                tmp_path,
                "interests: x\ntoken_budget:\n  cultivation_fraction: 1.5\n",
            )
        )


def test_negative_max_per_run_rejected(tmp_path):
    with pytest.raises(ConfigError, match="max_per_run"):
        load_config(
            _write(tmp_path, "interests: x\ntoken_budget:\n  max_per_run: -1\n")
        )


def test_missing_file_rejected(tmp_path):
    with pytest.raises(ConfigError, match="not found"):
        load_config(tmp_path / "nope.yml")


def test_secrets_default_empty(tmp_path):
    cfg = load_config(_write(tmp_path, "interests: x\n"))
    assert cfg.secrets == {}
    assert cfg.secret_env() == {}


def test_secrets_resolve_to_env_names(tmp_path):
    cfg = load_config(
        _write(
            tmp_path,
            """
            interests: x
            secrets:
              api_key: sk-test
              smtp_password: hunter2
              OPENROUTER_API_KEY: abc
            """,
        )
    )
    env = cfg.secret_env()
    assert env["LLM_API_KEY"] == "sk-test"
    assert env["SMTP_PASS"] == "hunter2"
    assert env["OPENROUTER_API_KEY"] == "abc"  # unknown keys pass through unchanged


def test_blank_secret_values_are_dropped(tmp_path):
    cfg = load_config(
        _write(
            tmp_path,
            "interests: x\nsecrets:\n  api_key: ''\n  smtp_host: ~\n",
        )
    )
    assert cfg.secrets == {}


def test_apply_secrets_does_not_override_environment(tmp_path):
    cfg = load_config(
        _write(
            tmp_path,
            "interests: x\nsecrets:\n  api_key: from-file\n  smtp_user: u@x\n",
        )
    )
    env = {"LLM_API_KEY": "from-env"}  # already set -> must win
    applied = cfg.apply_secrets_to_env(env)
    assert env["LLM_API_KEY"] == "from-env"  # untouched
    assert env["SMTP_USER"] == "u@x"  # gap filled
    assert applied == ["SMTP_USER"]


def test_secrets_must_be_mapping(tmp_path):
    with pytest.raises(ConfigError, match="secrets"):
        load_config(_write(tmp_path, "interests: x\nsecrets:\n  - nope\n"))
