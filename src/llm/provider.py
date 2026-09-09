"""Abstract base interface for LLM providers."""

import time
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Tuple, Type, TypeVar
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class LLMProvider(ABC):
    """Base class defining standard interface for LLM integration."""

    provider_name: str = "base"
    model_name: str = "unknown"

    @abstractmethod
    async def generate_structured(
        self,
        prompt: str,
        response_model: Type[T],
        system_prompt: Optional[str] = None,
    ) -> Tuple[T, Dict[str, Any]]:
        """Generate structured output validated against a Pydantic model.

        Returns:
            Tuple of (parsed_pydantic_instance, telemetry_dict)
            where telemetry_dict contains keys: 'tokens_prompt', 'tokens_completion', 'latency_ms', 'model'.
        """
        pass

    @abstractmethod
    async def generate_text(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
    ) -> Tuple[str, Dict[str, Any]]:
        """Generate plain text or markdown response with telemetry metadata."""
        pass
