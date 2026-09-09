"""LLM Providers factory and exports."""

import logging
from typing import Optional

from src.config import settings
from src.llm.provider import LLMProvider
from src.llm.mock_provider import MockLLMProvider
from src.llm.gemini_provider import GeminiLLMProvider
from src.llm.openai_provider import OpenAICompatibleProvider

logger = logging.getLogger("llm_factory")


def get_llm_provider(
    provider_name: Optional[str] = None,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
) -> LLMProvider:
    """Factory creating an LLM provider based on name and environment."""
    chosen = (provider_name or settings.default_llm_provider).lower()

    if chosen == "gemini":
        key = api_key or settings.gemini_api_key
        if not key:
            logger.warning("No GEMINI_API_KEY found in environment. Falling back to Mock provider.")
            return MockLLMProvider()
        return GeminiLLMProvider(api_key=key, model=model)

    elif chosen in ("openai", "chatgpt"):
        key = api_key or settings.openai_api_key
        if not key:
            logger.warning("No OPENAI_API_KEY found in environment. Falling back to Mock provider.")
            return MockLLMProvider()
        return OpenAICompatibleProvider(api_key=key, model=model)

    elif chosen == "mock":
        return MockLLMProvider()

    else:
        logger.warning(f"Unknown provider '{chosen}'. Using MockLLMProvider.")
        return MockLLMProvider()


__all__ = [
    "LLMProvider",
    "MockLLMProvider",
    "GeminiLLMProvider",
    "OpenAICompatibleProvider",
    "get_llm_provider",
]
