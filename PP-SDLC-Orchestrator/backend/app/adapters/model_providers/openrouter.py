"""Real network-calling ModelProvider backed by OpenRouter's OpenAI-compatible
chat completions API (https://openrouter.ai/api/v1/chat/completions).
"""

import httpx

from app.adapters.model_providers.base import ModelProviderError


class OpenRouterProvider:
    def __init__(self, *, api_key: str, model: str, base_url: str, timeout: float = 60.0):
        self._api_key = api_key
        self._model = model
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    def complete(self, *, system: str, user: str) -> str:
        try:
            response = httpx.post(
                f"{self._base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self._model,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    "temperature": 0.3,
                },
                timeout=self._timeout,
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise ModelProviderError(
                f"OpenRouter returned {exc.response.status_code}: {exc.response.text[:500]}"
            ) from exc
        except httpx.HTTPError as exc:
            raise ModelProviderError(f"OpenRouter request failed: {exc}") from exc

        data = response.json()
        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ModelProviderError(f"Unexpected OpenRouter response shape: {data}") from exc
