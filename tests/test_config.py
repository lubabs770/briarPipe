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
    assert cfg.provider.name == "anthropic"
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
              name: Anthropic
              model: claude-opus-4-8
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
    assert cfg.provider.name == "anthropic"
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
