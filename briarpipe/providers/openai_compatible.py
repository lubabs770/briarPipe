"""Generic OpenAI-compatible provider — bring your own key.

Talks to any endpoint that implements the OpenAI ``/chat/completions`` API, which
by now is the lingua franca: OpenAI, OpenRouter, Together, Groq, Mistral, DeepSeek,
a local Ollama / LM Studio, or Anthropic's own OpenAI-compatible endpoint. You
supply ``base_url`` + ``model`` and an API key (from an env var, default
``LLM_API_KEY``). No vendor SDK — just httpx — so swapping providers is config-only.
"""

from __future__ import annotations

import os

from . import Completion, Usage

DEFAULT_API_KEY_ENV = "LLM_API_KEY"


class OpenAICompatibleProvider:
    name = "openai-compatible"

    def __init__(
        self,
        model: str,
        base_url: str | None = None,
        api_key: str | None = None,
        api_key_env: str = DEFAULT_API_KEY_ENV,
    ) -> None:
        self.model = (model or "").strip()
        self.base_url = (base_url or "").rstrip("/")
        self._api_key = api_key or os.environ.get(api_key_env)
        self._api_key_env = api_key_env

    def complete(self, system: str, prompt: str, max_tokens: int) -> Completion:
        if not self.base_url:
            raise RuntimeError(
                "provider.base_url is not set; point it at your API endpoint, "
                "e.g. https://api.openai.com/v1 or https://openrouter.ai/api/v1"
            )
        if not self.model:
            raise RuntimeError(
                "provider.model is not set; choose a model your endpoint serves"
            )
        if not self._api_key:
            raise RuntimeError(
                f"no API key; set {self._api_key_env} (env var / Actions secret) "
                "or put it in the config secrets: block"
            )

        import httpx  # lazy so the package imports without the dep at test time

        resp = httpx.post(
            f"{self.base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self.model,
                "max_tokens": max_tokens,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
            },
            timeout=120.0,
        )
        resp.raise_for_status()
        data = resp.json()

        choice = (data.get("choices") or [{}])[0]
        text = ((choice.get("message") or {}).get("content")) or ""
        u = data.get("usage") or {}
        usage = Usage(
            input_tokens=int(u.get("prompt_tokens", 0) or 0),
            output_tokens=int(u.get("completion_tokens", 0) or 0),
        )
        return Completion(text=text, usage=usage)
