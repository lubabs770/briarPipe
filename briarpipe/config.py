"""Load and validate a briarPipe ``config.yml``.

The config is the single source of truth for an edition: what to cover, how often,
how much to spend, who writes it and in what voice, and where it goes. API keys are
deliberately *not* part of the config — they come from the environment.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

VALID_FREQUENCIES = ("daily", "weekly", "monthly")
VALID_SUMMARY_LENGTHS = ("short", "medium", "long")


class ConfigError(ValueError):
    """Raised when a config file is missing required fields or has bad values."""


@dataclass
class TokenBudget:
    max_per_run: int = 120_000
    cultivation_fraction: float = 0.2

    @property
    def cultivation_budget(self) -> int:
        return int(self.max_per_run * self.cultivation_fraction)

    @property
    def curation_budget(self) -> int:
        return self.max_per_run - self.cultivation_budget


@dataclass
class Provider:
    name: str = "anthropic"
    model: str = "claude-sonnet-4-6"


@dataclass
class Delivery:
    gateway: str = "markdown"
    to: str | None = None
    # Gateway-specific extras are kept verbatim for the gateway to interpret.
    options: dict[str, Any] = field(default_factory=dict)


@dataclass
class Output:
    max_stories: int = 12
    sections: list[str] = field(default_factory=lambda: ["Headlines"])
    summary_length: str = "medium"


@dataclass
class Config:
    interests: str
    frequency: str = "weekly"
    language: str = "en"
    timezone: str = "UTC"
    edition_name: str = "briarPipe"
    topics: list[str] = field(default_factory=list)
    token_budget: TokenBudget = field(default_factory=TokenBudget)
    bootstrap_sources: list[str] = field(default_factory=list)
    provider: Provider = field(default_factory=Provider)
    delivery: Delivery = field(default_factory=Delivery)
    output: Output = field(default_factory=Output)
    style: str = "clear and neutral"

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Config":
        if not isinstance(data, dict):
            raise ConfigError("config must be a YAML mapping at the top level")

        interests = data.get("interests")
        if not interests or not str(interests).strip():
            raise ConfigError("'interests' is required and cannot be empty")

        frequency = str(data.get("frequency", "weekly")).lower()
        if frequency not in VALID_FREQUENCIES:
            raise ConfigError(
                f"'frequency' must be one of {VALID_FREQUENCIES}, got {frequency!r}"
            )

        tb_raw = data.get("token_budget") or {}
        if not isinstance(tb_raw, dict):
            raise ConfigError("'token_budget' must be a mapping")
        token_budget = TokenBudget(
            max_per_run=_positive_int(tb_raw, "max_per_run", 120_000),
            cultivation_fraction=_fraction(tb_raw, "cultivation_fraction", 0.2),
        )

        prov_raw = data.get("provider") or {}
        if not isinstance(prov_raw, dict):
            raise ConfigError("'provider' must be a mapping")
        provider = Provider(
            name=str(prov_raw.get("name", "anthropic")).lower(),
            model=str(prov_raw.get("model", "claude-sonnet-4-6")),
        )

        del_raw = data.get("delivery") or {}
        if not isinstance(del_raw, dict):
            raise ConfigError("'delivery' must be a mapping")
        known = {"gateway", "to"}
        delivery = Delivery(
            gateway=str(del_raw.get("gateway", "markdown")).lower(),
            to=del_raw.get("to"),
            options={k: v for k, v in del_raw.items() if k not in known},
        )

        out_raw = data.get("output") or {}
        if not isinstance(out_raw, dict):
            raise ConfigError("'output' must be a mapping")
        summary_length = str(out_raw.get("summary_length", "medium")).lower()
        if summary_length not in VALID_SUMMARY_LENGTHS:
            raise ConfigError(
                f"'output.summary_length' must be one of {VALID_SUMMARY_LENGTHS}"
            )
        output = Output(
            max_stories=_positive_int(out_raw, "max_stories", 12),
            sections=_str_list(out_raw.get("sections"), default=["Headlines"]),
            summary_length=summary_length,
        )

        return cls(
            interests=str(interests).strip(),
            frequency=frequency,
            language=str(data.get("language", "en")),
            timezone=str(data.get("timezone", "UTC")),
            edition_name=str(data.get("edition_name", "briarPipe")),
            topics=_str_list(data.get("topics"), default=[]),
            token_budget=token_budget,
            bootstrap_sources=_str_list(data.get("bootstrap_sources"), default=[]),
            provider=provider,
            delivery=delivery,
            output=output,
            style=str(data.get("style", "clear and neutral")).strip()
            or "clear and neutral",
        )


def load_config(path: str | Path) -> Config:
    """Read, parse and validate a config file, returning a :class:`Config`."""
    path = Path(path)
    if not path.exists():
        raise ConfigError(f"config file not found: {path}")
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:  # pragma: no cover - passthrough of parse error
        raise ConfigError(f"could not parse {path}: {exc}") from exc
    return Config.from_dict(data or {})


# --- small validation helpers ------------------------------------------------


def _positive_int(d: dict[str, Any], key: str, default: int) -> int:
    value = d.get(key, default)
    try:
        value = int(value)
    except (TypeError, ValueError):
        raise ConfigError(f"'{key}' must be an integer, got {value!r}") from None
    if value <= 0:
        raise ConfigError(f"'{key}' must be positive, got {value}")
    return value


def _fraction(d: dict[str, Any], key: str, default: float) -> float:
    value = d.get(key, default)
    try:
        value = float(value)
    except (TypeError, ValueError):
        raise ConfigError(f"'{key}' must be a number, got {value!r}") from None
    if not 0.0 <= value <= 1.0:
        raise ConfigError(f"'{key}' must be between 0 and 1, got {value}")
    return value


def _str_list(value: Any, default: list[str]) -> list[str]:
    if value is None:
        return list(default)
    if isinstance(value, str):
        return [value]
    if isinstance(value, (list, tuple)):
        return [str(v).strip() for v in value if str(v).strip()]
    raise ConfigError(f"expected a list of strings, got {type(value).__name__}")
