import abc
import time
from typing import List, Optional
from app.llm.schemas import LLMMessage, LLMResponse, ProviderName
from app.core.logging import logger


class BaseLLMClient(abc.ABC):
    @property
    @abc.abstractmethod
    def provider_name(self) -> ProviderName:
        pass

    @abc.abstractmethod
    async def generate(
        self,
        messages: List[LLMMessage],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        timeout: Optional[float] = None,
    ) -> LLMResponse:
        """Generate response from LLM."""
        pass

    @abc.abstractmethod
    async def is_healthy(self) -> bool:
        """Check provider connectivity/credentials."""
        pass

    @abc.abstractmethod
    async def stream_generate(
        self,
        messages: List[LLMMessage],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        timeout: Optional[float] = None,
    ):
        """Asynchronously stream text tokens incrementally."""
        pass

