import asyncio
import time
from typing import List, Optional
from google import genai
from google.genai import types
from google.genai.errors import APIError
from app.llm.base import BaseLLMClient
from app.llm.schemas import LLMMessage, LLMResponse, ProviderName
from app.core.config import settings
from app.core.logging import logger


class GeminiClient(BaseLLMClient):
    def __init__(
        self,
        api_key: Optional[str] = None,
        default_model: Optional[str] = None,
        max_retries: Optional[int] = None,
        timeout: Optional[float] = None,
    ):
        self._api_key = api_key or settings.GEMINI_API_KEY
        self._default_model = default_model or settings.GEMINI_MODEL
        self._max_retries = max_retries or settings.GEMINI_MAX_RETRIES
        self._timeout = timeout or settings.GEMINI_TIMEOUT_SECONDS
        self._client: Optional[genai.Client] = None

    @property
    def provider_name(self) -> ProviderName:
        return ProviderName.GEMINI

    def _get_client(self) -> genai.Client:
        if not self._client:
            if not self._api_key:
                raise ValueError("GEMINI_API_KEY is not configured.")
            self._client = genai.Client(api_key=self._api_key)
        return self._client

    async def is_healthy(self) -> bool:
        if not self._api_key or self._api_key.startswith("placeholder"):
            return False
        try:
            client = self._get_client()
            res = await client.aio.models.generate_content(
                model=settings.GEMINI_FLASH_MODEL,
                contents="ping",
                config=types.GenerateContentConfig(max_output_tokens=10),
            )
            return bool(res.text)
        except Exception as e:
            logger.warning(f"Gemini health check failed: {e}")
            return False

    async def generate(
        self,
        messages: List[LLMMessage],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        timeout: Optional[float] = None,
    ) -> LLMResponse:
        client = self._get_client()
        target_model = model or self._default_model

        # Extract system prompt if present
        system_instruction = None
        user_contents = []

        for msg in messages:
            if msg.role == "system":
                system_instruction = msg.content
            else:
                user_contents.append(f"{msg.role.capitalize()}: {msg.content}")

        combined_prompt = "\n\n".join(user_contents)

        config = types.GenerateContentConfig(
            system_instruction=system_instruction,
            temperature=temperature,
            max_output_tokens=max_tokens,
        )

        retries = 0
        backoff_delay = 1.0

        while retries <= self._max_retries:
            start_time = time.perf_counter()
            try:
                logger.info(
                    f"[Gemini] Dispatching request model={target_model} retries={retries}/{self._max_retries}"
                )
                res = await client.aio.models.generate_content(
                    model=target_model,
                    contents=combined_prompt,
                    config=config,
                )
                latency = (time.perf_counter() - start_time) * 1000.0
                text_content = res.text or ""

                tokens = None
                if hasattr(res, "usage_metadata") and res.usage_metadata:
                    tokens = getattr(res.usage_metadata, "total_token_count", None)

                logger.info(
                    f"[Gemini] Success model={target_model} latency={latency:.1f}ms tokens={tokens}"
                )
                return LLMResponse(
                    content=text_content,
                    provider=self.provider_name,
                    model=target_model,
                    tokens_used=tokens,
                    latency_ms=latency,
                    finish_reason="STOP",
                )

            except APIError as e:
                # Check for 429 quota exhaustion or 5xx
                status_code = getattr(e, "code", None)
                if status_code in (429, 500, 503, 504):
                    retries += 1
                    logger.warning(
                        f"[Gemini Transient Error {status_code}] Attempt {retries}/{self._max_retries}: {e}"
                    )
                    if retries > self._max_retries:
                        raise
                    await asyncio.sleep(backoff_delay)
                    backoff_delay *= 2.0
                else:
                    logger.error(f"[Gemini Non-retryable API Error]: {e}")
                    raise

            except Exception as e:
                logger.error(f"[Gemini Unexpected Error]: {e}")
                raise

    async def stream_generate(
        self,
        messages: List[LLMMessage],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        timeout: Optional[float] = None,
    ):
        """Asynchronously stream tokens from Gemini API."""
        client = self._get_client()
        target_model = model or self._default_model

        system_instruction = None
        user_contents = []

        for msg in messages:
            if msg.role == "system":
                system_instruction = msg.content
            else:
                user_contents.append(f"{msg.role.capitalize()}: {msg.content}")

        combined_prompt = "\n\n".join(user_contents)
        config = types.GenerateContentConfig(
            system_instruction=system_instruction,
            temperature=temperature,
            max_output_tokens=max_tokens,
        )

        response_stream = await client.aio.models.generate_content_stream(
            model=target_model,
            contents=combined_prompt,
            config=config,
        )

        async for chunk in response_stream:
            if chunk.text:
                yield chunk.text

