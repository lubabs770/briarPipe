import pytest

from briarpipe.providers import get_provider
from briarpipe.providers.openai_compatible import OpenAICompatibleProvider


def test_builtin_aliases_resolve_to_generic_provider():
    for name in ("openai-compatible", "openai", "generic"):
        prov = get_provider(name, "some-model", base_url="https://api.example/v1",
                            api_key="k")
        assert isinstance(prov, OpenAICompatibleProvider)


def test_unknown_provider_rejected():
    with pytest.raises(ValueError, match="unknown provider"):
        get_provider("anthropic", "claude")  # vendor SDKs are gone; generic only


def test_complete_requires_base_url():
    prov = OpenAICompatibleProvider("m", base_url="", api_key="k")
    with pytest.raises(RuntimeError, match="base_url"):
        prov.complete("sys", "hi", 100)


def test_complete_requires_model():
    prov = OpenAICompatibleProvider("", base_url="https://api.example/v1", api_key="k")
    with pytest.raises(RuntimeError, match="model"):
        prov.complete("sys", "hi", 100)


def test_complete_requires_api_key(monkeypatch):
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    prov = OpenAICompatibleProvider("m", base_url="https://api.example/v1", api_key=None)
    with pytest.raises(RuntimeError, match="API key"):
        prov.complete("sys", "hi", 100)
