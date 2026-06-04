"""AI provider abstraction.

The pipeline only ever talks to a :class:`Provider`. Concrete providers wrap a
vendor SDK and, crucially, report token usage per call so the pipeline can hold
each phase to its slice of the budget. Adding a new provider is a matter of
implementing :meth:`Provider.complete` and registering it — the pipeline never
changes.
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


# name -> factory(model) -> Provider
_REGISTRY: dict[str, Callable[[str], Provider]] = {}


def register_provider(name: str, factory: Callable[[str], Provider]) -> None:
    _REGISTRY[name.lower()] = factory


def get_provider(name: str, model: str) -> Provider:
    key = name.lower()
    if key not in _REGISTRY:
        raise ValueError(
            f"unknown provider {name!r}; available: {sorted(_REGISTRY)}"
        )
    return _REGISTRY[key](model)


# Register built-in providers. Imports are guarded so the package still loads
# (e.g. for tests) when an optional SDK isn't installed.
def _register_builtins() -> None:
    try:
        from .anthropic import AnthropicProvider

        register_provider("anthropic", lambda model: AnthropicProvider(model))
    except Exception:  # pragma: no cover - optional dependency missing
        pass


_register_builtins()
