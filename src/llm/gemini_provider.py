"""Google Gemini LLM Provider using the modern google-genai SDK."""

import json
import logging
import time
from typing import Any, Dict, Optional, Tuple, Type, TypeVar
from pydantic import BaseModel

from src.config import settings
from src.llm.provider import LLMProvider

logger = logging.getLogger("gemini_provider")
T = TypeVar("T", bound=BaseModel)


class GeminiLLMProvider(LLMProvider):
    """Provider integrating Google Gemini API with native structured output."""

    provider_name: str = "gemini"

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key or settings.gemini_api_key
        self.model_name = model or settings.gemini_model
        self._client = None

    def _get_client(self):
        if self._client is None:
            if not self.api_key:
                raise ValueError("GEMINI_API_KEY is not set. Provide it in .env or via config.")
            from google import genai
            self._client = genai.Client(api_key=self.api_key)
        return self._client

    async def generate_structured(
        self,
        prompt: str,
        response_model: Type[T],
        system_prompt: Optional[str] = None,
    ) -> Tuple[T, Dict[str, Any]]:
        client = self._get_client()
        from google.genai import types

        start_time = time.perf_counter()

        config = types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=response_model,
            system_instruction=system_prompt,
            temperature=0.2,
        )

        try:
            # google-genai async call
            response = await client.aio.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=config,
            )
        except Exception as exc:
            logger.error(f"Gemini API error during generate_content: {exc}")
            raise

        latency_ms = int((time.perf_counter() - start_time) * 1000)

        # Parse text into Pydantic model
        raw_text = response.text or ""
        # Strip markdown fences if present
        cleaned_text = raw_text.strip()
        if cleaned_text.startswith("```json"):
            cleaned_text = cleaned_text[7:]
        if cleaned_text.startswith("```"):
            cleaned_text = cleaned_text[3:]
        if cleaned_text.endswith("```"):
            cleaned_text = cleaned_text[:-3]
        cleaned_text = cleaned_text.strip()

        parsed_model = response_model.model_validate_json(cleaned_text)

        # Telemetry
        tokens_prompt = getattr(response.usage_metadata, "prompt_token_count", 0) or 0
        tokens_completion = getattr(response.usage_metadata, "candidates_token_count", 0) or 0

        telemetry = {
            "model": self.model_name,
            "provider": self.provider_name,
            "tokens_prompt": tokens_prompt,
            "tokens_completion": tokens_completion,
            "latency_ms": latency_ms,
        }

        return parsed_model, telemetry

    async def generate_text(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
    ) -> Tuple[str, Dict[str, Any]]:
        client = self._get_client()
        from google.genai import types

        start_time = time.perf_counter()
        config = types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=0.4,
        )

        response = await client.aio.models.generate_content(
            model=self.model_name,
            contents=prompt,
            config=config,
        )

        latency_ms = int((time.perf_counter() - start_time) * 1000)
        tokens_prompt = getattr(response.usage_metadata, "prompt_token_count", 0) or 0
        tokens_completion = getattr(response.usage_metadata, "candidates_token_count", 0) or 0

        telemetry = {
            "model": self.model_name,
            "provider": self.provider_name,
            "tokens_prompt": tokens_prompt,
            "tokens_completion": tokens_completion,
            "latency_ms": latency_ms,
        }

        return response.text or "", telemetry
