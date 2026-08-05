import httpx
import pytest

from app.adapters.model_providers.base import ModelProviderError
from app.adapters.model_providers.openrouter import OpenRouterProvider


def _provider() -> OpenRouterProvider:
    return OpenRouterProvider(
        api_key="test-key", model="test/model", base_url="https://openrouter.ai/api/v1"
    )


def test_complete_sends_expected_request_and_parses_response(monkeypatch):
    captured = {}

    def fake_post(url, *, headers, json, timeout):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        request = httpx.Request("POST", url)
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "hello world"}}]},
            request=request,
        )

    monkeypatch.setattr(httpx, "post", fake_post)

    result = _provider().complete(system="sys prompt", user="user prompt")

    assert result == "hello world"
    assert captured["url"] == "https://openrouter.ai/api/v1/chat/completions"
    assert captured["headers"]["Authorization"] == "Bearer test-key"
    assert captured["json"]["model"] == "test/model"
    assert captured["json"]["messages"] == [
        {"role": "system", "content": "sys prompt"},
        {"role": "user", "content": "user prompt"},
    ]


def test_non_200_response_raises_model_provider_error(monkeypatch):
    def fake_post(url, *, headers, json, timeout):
        request = httpx.Request("POST", url)
        return httpx.Response(401, json={"error": "invalid api key"}, request=request)

    monkeypatch.setattr(httpx, "post", fake_post)

    with pytest.raises(ModelProviderError):
        _provider().complete(system="s", user="u")


def test_network_error_raises_model_provider_error(monkeypatch):
    def fake_post(url, *, headers, json, timeout):
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr(httpx, "post", fake_post)

    with pytest.raises(ModelProviderError):
        _provider().complete(system="s", user="u")


def test_unexpected_response_shape_raises_model_provider_error(monkeypatch):
    def fake_post(url, *, headers, json, timeout):
        request = httpx.Request("POST", url)
        return httpx.Response(200, json={"unexpected": "shape"}, request=request)

    monkeypatch.setattr(httpx, "post", fake_post)

    with pytest.raises(ModelProviderError):
        _provider().complete(system="s", user="u")
