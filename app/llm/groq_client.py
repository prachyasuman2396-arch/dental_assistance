import asyncio
import time
from typing import List, Optional
from groq import AsyncGroq, APIError, RateLimitError, APITimeoutError
from app.llm.base import BaseLLMClient
from app.llm.schemas import LLMMessage, LLMResponse, ProviderName
from app.core.config import settings
from app.core.logging import logger


class GroqClient(BaseLLMClient):
    def __init__(
        self,
        api_key: Optional[str] = None,
        default_model: Optional[str] = None,
        max_retries: Optional[int] = None,
        timeout: Optional[float] = None,
    ):
        self._api_key = api_key or settings.GROQ_API_KEY
        self._default_model = default_model or settings.GROQ_MODEL
        self._max_retries = max_retries or settings.GROQ_MAX_RETRIES
        self._timeout = timeout or settings.GROQ_TIMEOUT_SECONDS
        self._client: Optional[AsyncGroq] = None

    @property
    def provider_name(self) -> ProviderName:
        return ProviderName.GROQ

    def _get_client(self) -> AsyncGroq:
        if not self._client:
            if not self._api_key:
                raise ValueError("GROQ_API_KEY is not configured.")
            self._client = AsyncGroq(api_key=self._api_key, timeout=self._timeout)
        return self._client

    async def is_healthy(self) -> bool:
        if not self._api_key or self._api_key.startswith("gsk_placeholder"):
            return False
        try:
            client = self._get_client()
            # Lightweight health ping using fast model
            res = await client.chat.completions.create(
                model=settings.GROQ_FAST_MODEL,
                messages=[{"role": "user", "content": "ping"}],
                max_tokens=2,
            )
            return bool(res.choices)
        except Exception as e:
            logger.warning(f"Groq health check failed: {e}")
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
        req_timeout = timeout or self._timeout
        formatted_messages = [{"role": m.role, "content": m.content} for m in messages]

        retries = 0
        backoff_delay = 1.0

        while retries <= self._max_retries:
            start_time = time.perf_counter()
            try:
                logger.info(
                    f"[Groq] Dispatching request model={target_model} retries={retries}/{self._max_retries}"
                )
                res = await client.chat.completions.create(
                    model=target_model,
                    messages=formatted_messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    timeout=req_timeout,
                )
                latency = (time.perf_counter() - start_time) * 1000.0
                choice = res.choices[0]
                tokens = res.usage.total_tokens if res.usage else None

                logger.info(
                    f"[Groq] Success model={target_model} latency={latency:.1f}ms tokens={tokens}"
                )
                return LLMResponse(
                    content=choice.message.content or "",
                    provider=self.provider_name,
                    model=target_model,
                    tokens_used=tokens,
                    latency_ms=latency,
                    finish_reason=choice.finish_reason,
                )

            except RateLimitError as e:
                retries += 1
                logger.warning(f"[Groq RateLimit] Attempt {retries}/{self._max_retries}: {e}")
                if retries > self._max_retries:
                    raise
                await asyncio.sleep(backoff_delay)
                backoff_delay *= 2.0

            except APITimeoutError as e:
                retries += 1
                logger.warning(f"[Groq Timeout] Attempt {retries}/{self._max_retries}: {e}")
                if retries > self._max_retries:
                    raise
                await asyncio.sleep(backoff_delay)
                backoff_delay *= 1.5

            except APIError as e:
                # 5xx errors can be retried
                if getattr(e, "status_code", 0) in (500, 502, 503, 504):
                    retries += 1
                    logger.warning(f"[Groq Server Error] Attempt {retries}/{self._max_retries}: {e}")
                    if retries > self._max_retries:
                        raise
                    await asyncio.sleep(backoff_delay)
                    backoff_delay *= 2.0
                else:
                    logger.error(f"[Groq Non-retryable API Error]: {e}")
                    raise

            except Exception as e:
                logger.error(f"[Groq Unexpected Error]: {e}")
                raise

    async def stream_generate(
        self,
        messages: List[LLMMessage],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        timeout: Optional[float] = None,
    ):
        """Asynchronously stream tokens from Groq API."""
        client = self._get_client()
        target_model = model or self._default_model
        req_timeout = timeout or self._timeout
        formatted_messages = [{"role": m.role, "content": m.content} for m in messages]

        stream = await client.chat.completions.create(
            model=target_model,
            messages=formatted_messages,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=req_timeout,
            stream=True,
        )

        async for chunk in stream:
            delta = chunk.choices[0].delta.content if chunk.choices else None
            if delta:
                yield delta

