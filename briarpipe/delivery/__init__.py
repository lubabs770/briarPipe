"""Delivery gateways.

A dated Markdown file is always written to ``editions/`` by the store; that's the
baseline and never needs configuring. *Gateways* are optional push channels on top
of that — email today, WhatsApp/Telegram/webhooks later — all behind one
:meth:`Gateway.send` call so the pipeline stays channel-agnostic.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Protocol


@dataclass
class Edition:
    """A rendered edition handed to a gateway for delivery."""

    title: str
    date: str
    markdown: str
    path: str = ""  # where the store wrote it, if applicable


class Gateway(Protocol):
    name: str

    def send(self, edition: Edition) -> str:  # pragma: no cover - interface
        """Deliver the edition. Returns a short human-readable status line."""
        ...


# name -> factory(to, options) -> Gateway
_REGISTRY: dict[str, Callable[[str | None, dict[str, Any]], Gateway]] = {}


def register_gateway(
    name: str, factory: Callable[[str | None, dict[str, Any]], Gateway]
) -> None:
    _REGISTRY[name.lower()] = factory


def get_gateway(name: str, to: str | None, options: dict[str, Any] | None = None) -> Gateway:
    key = name.lower()
    if key not in _REGISTRY:
        raise ValueError(f"unknown delivery gateway {name!r}; available: {sorted(_REGISTRY)}")
    return _REGISTRY[key](to, options or {})


from .markdown import MarkdownGateway  # noqa: E402
from .email import EmailGateway  # noqa: E402

register_gateway("markdown", lambda to, opts: MarkdownGateway())
register_gateway("email", lambda to, opts: EmailGateway(to, opts))
