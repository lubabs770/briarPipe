"""Anthropic provider — the reference implementation.

Reads its API key from ``ANTHROPIC_API_KEY`` (a secret / env var, never config).
Other providers follow the same shape: wrap the SDK, return text + token usage.
"""

from __future__ import annotations

import os

from . import Completion, Usage


class AnthropicProvider:
    name = "anthropic"

    def __init__(self, model: str, api_key: str | None = None) -> None:
        self.model = model
        self._api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        self._client = None

    def _ensure_client(self):
        if self._client is None:
            if not self._api_key:
                raise RuntimeError(
                    "ANTHROPIC_API_KEY is not set; add it as a secret/env var"
                )
            import anthropic  # type: ignore

            self._client = anthropic.Anthropic(api_key=self._api_key)
        return self._client

    def complete(self, system: str, prompt: str, max_tokens: int) -> Completion:
        client = self._ensure_client()
        resp = client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": prompt}],
        )
        text = "".join(
            block.text for block in resp.content if getattr(block, "type", "") == "text"
        )
        usage = Usage(
            input_tokens=getattr(resp.usage, "input_tokens", 0),
            output_tokens=getattr(resp.usage, "output_tokens", 0),
        )
        return Completion(text=text, usage=usage)
