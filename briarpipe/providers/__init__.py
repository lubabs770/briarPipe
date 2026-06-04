"""AI provider abstraction — bring your own key.

The pipeline only ever talks to a :class:`Provider`. The built-in provider is a
generic **OpenAI-compatible** client (see :mod:`.openai_compatible`) that works
against any endpoint speaking the ``/chat/completions`` API — no vendor is special.
Providers report token usage per call so the pipeline can hold each phase to its
slice of the budget. Adding another provider is a matter of implementing
:meth:`Provider.complete` and registering it — the pipeline never changes.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Protocol


@dataclass
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0

    @property
    def total(self) -> int:
        return self.input_tokens + self.output_tokens

    def __add__(self, other: "Usage") -> "Usage":
        return Usage(
            self.input_tokens + other.input_tokens,
            self.output_tokens + other.output_tokens,
        )


@dataclass
class Completion:
    text: str
    usage: Usage


class Provider(Protocol):
    """Minimal surface every provider must offer."""

    name: str

    def complete(
        self, system: str, prompt: str, max_tokens: int
    ) -> Completion:  # pragma: no cover - interface
        ...


# name -> factory(model, base_url, api_key) -> Provider
ProviderFactory = Callable[[str, str, "str | None"], Provider]
_REGISTRY: dict[str, ProviderFactory] = {}


def register_provider(name: str, factory: ProviderFactory) -> None:
    _REGISTRY[name.lower()] = factory


def get_provider(
    name: str, model: str, *, base_url: str = "", api_key: str | None = None
) -> Provider:
    key = name.lower()
    if key not in _REGISTRY:
        raise ValueError(
            f"unknown provider {name!r}; available: {sorted(_REGISTRY)}"
        )
    return _REGISTRY[key](model, base_url, api_key)


# The built-in is the generic OpenAI-compatible client; it needs no SDK (just
# httpx, used lazily), so registration is unconditional. Register it under a few
# friendly aliases that all mean "an endpoint that speaks /chat/completions".
def _register_builtins() -> None:
    from .openai_compatible import OpenAICompatibleProvider

    def factory(model: str, base_url: str, api_key: str | None) -> Provider:
        return OpenAICompatibleProvider(model, base_url=base_url, api_key=api_key)

    for alias in ("openai-compatible", "openai", "generic"):
        register_provider(alias, factory)


_register_builtins()
