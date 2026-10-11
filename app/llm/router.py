from typing import List, Optional, Dict
from app.llm.schemas import (
    TaskType,
    ComplexityLevel,
    Capability,
    ProviderName,
    SelectedModelInfo,
    LLMMessage,
    LLMResponse,
)
from app.llm.base import BaseLLMClient
from app.llm.groq_client import GroqClient
from app.llm.gemini_client import GeminiClient
from app.core.config import settings
from app.core.logging import logger


class LLMRouter:
    def __init__(
        self,
        groq_client: Optional[BaseLLMClient] = None,
        gemini_client: Optional[BaseLLMClient] = None,
    ):
        self.groq_client = groq_client or GroqClient()
        self.gemini_client = gemini_client or GeminiClient()

    def select_provider(
        self,
        task_type: TaskType,
        complexity: ComplexityLevel = ComplexityLevel.LOW,
        context_length: int = 0,
        required_capabilities: Optional[List[Capability]] = None,
        provider_health: Optional[Dict[str, bool]] = None,
    ) -> SelectedModelInfo:
        """
        Intelligently select the best provider and model based on task type,
        complexity, context window, required capabilities, and provider health.
        """
        req_caps = set(required_capabilities or [])
        health = provider_health or {}
        groq_healthy = health.get("groq", True)
        gemini_healthy = health.get("gemini", True)

        # 1. Multimodal tasks strictly require Gemini
        if Capability.MULTIMODAL in req_caps or task_type == TaskType.MULTIMODAL:
            if not gemini_healthy or not settings.ENABLE_GEMINI:
                raise ValueError("Multimodal analysis requires Gemini, but Gemini is disabled or unhealthy.")
            return SelectedModelInfo(
                provider=ProviderName.GEMINI,
                model=settings.GEMINI_MODEL,
                timeout_seconds=settings.GEMINI_TIMEOUT_SECONDS,
                max_retries=settings.GEMINI_MAX_RETRIES,
                fallback_provider=None,
                fallback_model=None,
            )

        # 2. Long context (> 12,000 characters) or deep multi-source research synthesis prefers Gemini
        if (
            context_length > 12000
            or task_type == TaskType.RESEARCH_SYNTHESIS
            or (task_type == TaskType.TUTOR and complexity == ComplexityLevel.HIGH)
        ):
            if settings.ENABLE_GEMINI and gemini_healthy:
                return SelectedModelInfo(
                    provider=ProviderName.GEMINI,
                    model=settings.GEMINI_MODEL,
                    timeout_seconds=settings.GEMINI_TIMEOUT_SECONDS,
                    max_retries=settings.GEMINI_MAX_RETRIES,
                    fallback_provider=ProviderName.GROQ if groq_healthy else None,
                    fallback_model=settings.GROQ_MODEL if groq_healthy else None,
                )

        # 3. Fast tasks (classification, query rewriting, fast conversation, study cards, short verification)
        # prefer Groq for ultra-low latency
        if task_type in (
            TaskType.CLASSIFICATION,
            TaskType.CONVERSATION,
            TaskType.STUDY_GENERATION,
            TaskType.VERIFICATION,
        ) or complexity == ComplexityLevel.LOW:
            if groq_healthy:
                fast_model = (
                    settings.GROQ_FAST_MODEL
                    if task_type == TaskType.CLASSIFICATION
                    else settings.GROQ_MODEL
                )
                return SelectedModelInfo(
                    provider=ProviderName.GROQ,
                    model=fast_model,
                    timeout_seconds=settings.GROQ_TIMEOUT_SECONDS,
                    max_retries=settings.GROQ_MAX_RETRIES,
                    fallback_provider=ProviderName.GEMINI if (settings.ENABLE_GEMINI and gemini_healthy) else None,
                    fallback_model=settings.GEMINI_FLASH_MODEL if (settings.ENABLE_GEMINI and gemini_healthy) else None,
                )

        # 4. Default provider fallback based on configuration
        if settings.DEFAULT_LLM_PROVIDER.lower() == "gemini" and settings.ENABLE_GEMINI and gemini_healthy:
            return SelectedModelInfo(
                provider=ProviderName.GEMINI,
                model=settings.GEMINI_MODEL,
                timeout_seconds=settings.GEMINI_TIMEOUT_SECONDS,
                max_retries=settings.GEMINI_MAX_RETRIES,
                fallback_provider=ProviderName.GROQ if groq_healthy else None,
                fallback_model=settings.GROQ_MODEL if groq_healthy else None,
            )

        # Standard default is Groq
        if groq_healthy:
            return SelectedModelInfo(
                provider=ProviderName.GROQ,
                model=settings.GROQ_MODEL,
                timeout_seconds=settings.GROQ_TIMEOUT_SECONDS,
                max_retries=settings.GROQ_MAX_RETRIES,
                fallback_provider=ProviderName.GEMINI if (settings.ENABLE_GEMINI and gemini_healthy) else None,
                fallback_model=settings.GEMINI_FLASH_MODEL if (settings.ENABLE_GEMINI and gemini_healthy) else None,
            )
        elif settings.ENABLE_GEMINI and gemini_healthy:
            return SelectedModelInfo(
                provider=ProviderName.GEMINI,
                model=settings.GEMINI_FLASH_MODEL,
                timeout_seconds=settings.GEMINI_TIMEOUT_SECONDS,
                max_retries=settings.GEMINI_MAX_RETRIES,
                fallback_provider=None,
                fallback_model=None,
            )
        else:
            raise RuntimeError("No healthy LLM provider is currently available.")

    async def execute_with_fallback(
        self,
        task_type: TaskType,
        messages: List[LLMMessage],
        complexity: ComplexityLevel = ComplexityLevel.LOW,
        context_length: int = 0,
        required_capabilities: Optional[List[Capability]] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
    ) -> LLMResponse:
        """
        Executes query with the selected provider, and falls back gracefully
        if the primary provider encounters an error.
        """
        routing_info = self.select_provider(
            task_type=task_type,
            complexity=complexity,
            context_length=context_length,
            required_capabilities=required_capabilities,
        )

        primary_client = (
            self.groq_client if routing_info.provider == ProviderName.GROQ else self.gemini_client
        )

        try:
            return await primary_client.generate(
                messages=messages,
                model=routing_info.model,
                temperature=temperature,
                max_tokens=max_tokens,
                timeout=routing_info.timeout_seconds,
            )
        except Exception as primary_error:
            logger.warning(
                f"Primary provider {routing_info.provider.value} failed: {primary_error}. Evaluating fallback..."
            )

            if routing_info.fallback_provider and routing_info.fallback_model:
                fallback_client = (
                    self.groq_client
                    if routing_info.fallback_provider == ProviderName.GROQ
                    else self.gemini_client
                )
                logger.info(
                    f"Switching to fallback provider {routing_info.fallback_provider.value} (model={routing_info.fallback_model})"
                )
                try:
                    return await fallback_client.generate(
                        messages=messages,
                        model=routing_info.fallback_model,
                        temperature=temperature,
                        max_tokens=max_tokens,
                    )
                except Exception as fallback_error:
                    logger.error(
                        f"Fallback provider {routing_info.fallback_provider.value} also failed: {fallback_error}"
                    )
                    raise fallback_error
            else:
                raise primary_error
