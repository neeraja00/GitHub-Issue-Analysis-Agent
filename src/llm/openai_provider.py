"""OpenAI-compatible and Claude LLM Provider using direct httpx calls."""

import json
import logging
import time
from typing import Any, Dict, Optional, Tuple, Type, TypeVar
import httpx
from pydantic import BaseModel

from src.config import settings
from src.llm.provider import LLMProvider

logger = logging.getLogger("openai_provider")
T = TypeVar("T", bound=BaseModel)


class OpenAICompatibleProvider(LLMProvider):
    """Provider for OpenAI-compatible REST APIs."""

    provider_name: str = "openai"

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        base_url: str = "https://api.openai.com/v1",
    ):
        self.api_key = api_key or settings.openai_api_key
        self.model_name = model or settings.openai_model
        self.base_url = base_url.rstrip("/")

    async def generate_structured(
        self,
        prompt: str,
        response_model: Type[T],
        system_prompt: Optional[str] = None,
    ) -> Tuple[T, Dict[str, Any]]:
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY is not configured.")

        schema = response_model.model_json_schema()
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model_name,
            "messages": messages,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": response_model.__name__,
                    "schema": schema,
                    "strict": True,
                },
            },
            "temperature": 0.2,
        }

        start_time = time.perf_counter()
        async with httpx.AsyncClient(timeout=45.0) as client:
            resp = await client.post(f"{self.base_url}/chat/completions", headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()

        latency_ms = int((time.perf_counter() - start_time) * 1000)
        content = data["choices"][0]["message"]["content"]
        parsed = response_model.model_validate_json(content)

        usage = data.get("usage", {})
        telemetry = {
            "model": self.model_name,
            "provider": self.provider_name,
            "tokens_prompt": usage.get("prompt_tokens", 0),
            "tokens_completion": usage.get("completion_tokens", 0),
            "latency_ms": latency_ms,
        }
        return parsed, telemetry

    async def generate_text(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
    ) -> Tuple[str, Dict[str, Any]]:
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY is not configured.")

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model_name,
            "messages": messages,
            "temperature": 0.4,
        }

        start_time = time.perf_counter()
        async with httpx.AsyncClient(timeout=45.0) as client:
            resp = await client.post(f"{self.base_url}/chat/completions", headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()

        latency_ms = int((time.perf_counter() - start_time) * 1000)
        content = data["choices"][0]["message"]["content"]
        usage = data.get("usage", {})
        telemetry = {
            "model": self.model_name,
            "provider": self.provider_name,
            "tokens_prompt": usage.get("prompt_tokens", 0),
            "tokens_completion": usage.get("completion_tokens", 0),
            "latency_ms": latency_ms,
        }
        return content, telemetry
