"""The always-on baseline gateway.

The edition Markdown is written to ``editions/`` by the store regardless; this
gateway simply acknowledges that artifact so "markdown" is a valid, no-extra-setup
delivery choice.
"""

from __future__ import annotations

from . import Edition


class MarkdownGateway:
    name = "markdown"

    def send(self, edition: Edition) -> str:
        where = edition.path or "editions/"
        return f"edition written to {where}"
