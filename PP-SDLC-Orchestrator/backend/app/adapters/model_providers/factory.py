"""Resolves the configured ModelProvider from settings at call time (not
import time), so it always reflects whatever's currently in backend/.env.

Tests never hit this factory for real — see the autouse `stub_model_provider`
fixture in tests/conftest.py, which monkeypatches `get_model_provider`
itself so the full suite runs with zero network calls and zero cost.
"""

from app.adapters.model_providers.base import ModelProvider, ModelProviderError
from app.adapters.model_providers.openrouter import OpenRouterProvider
from app.config import get_settings


def get_model_provider() -> ModelProvider:
    settings = get_settings()
    if not settings.openrouter_api_key:
        raise ModelProviderError(
            "No LLM provider configured. Set PPSDLC_OPENROUTER_API_KEY in backend/.env "
            "to enable agents running with `runtime: llm`."
        )
    return OpenRouterProvider(
        api_key=settings.openrouter_api_key,
        model=settings.openrouter_model,
        base_url=settings.openrouter_base_url,
    )
