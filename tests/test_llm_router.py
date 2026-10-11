import pytest
from unittest.mock import AsyncMock
from app.llm.schemas import (
    TaskType,
    ComplexityLevel,
    Capability,
    ProviderName,
    LLMMessage,
    LLMResponse,
)
from app.llm.router import LLMRouter


def test_router_selects_groq_for_low_complexity(mock_router):
    selection = mock_router.select_provider(
        task_type=TaskType.TUTOR,
        complexity=ComplexityLevel.LOW,
    )
    assert selection.provider == ProviderName.GROQ
    assert selection.fallback_provider == ProviderName.GEMINI


def test_router_selects_fast_groq_for_classification(mock_router):
    selection = mock_router.select_provider(
        task_type=TaskType.CLASSIFICATION,
        complexity=ComplexityLevel.LOW,
    )
    assert selection.provider == ProviderName.GROQ


def test_router_selects_gemini_for_research_synthesis(mock_router):
    selection = mock_router.select_provider(
        task_type=TaskType.RESEARCH_SYNTHESIS,
        complexity=ComplexityLevel.HIGH,
        context_length=15000,
    )
    assert selection.provider == ProviderName.GEMINI
    assert selection.fallback_provider == ProviderName.GROQ


def test_router_selects_gemini_for_multimodal(mock_router):
    selection = mock_router.select_provider(
        task_type=TaskType.MULTIMODAL,
        required_capabilities=[Capability.MULTIMODAL],
    )
    assert selection.provider == ProviderName.GEMINI
    # Groq does not support multimodal, so fallback_provider must be None
    assert selection.fallback_provider is None


@pytest.mark.asyncio
async def test_router_fallback_execution_on_primary_failure(mock_groq_client, mock_gemini_client):
    # Groq fails with an error
    mock_groq_client.generate = AsyncMock(side_effect=RuntimeError("Groq 429 Rate Limit Exceeded"))
    router = LLMRouter(groq_client=mock_groq_client, gemini_client=mock_gemini_client)

    messages = [LLMMessage(role="user", content="Explain pulpitis.")]
    response = await router.execute_with_fallback(
        task_type=TaskType.TUTOR,
        messages=messages,
        complexity=ComplexityLevel.LOW,
    )

    # Should have called Groq, failed, then succeeded with Gemini
    assert mock_groq_client.generate.called
    assert mock_gemini_client.generate.called
    assert response.provider == ProviderName.GEMINI


@pytest.mark.asyncio
async def test_router_fails_gracefully_when_all_providers_fail(mock_groq_client, mock_gemini_client):
    mock_groq_client.generate = AsyncMock(side_effect=RuntimeError("Groq Down"))
    mock_gemini_client.generate = AsyncMock(side_effect=RuntimeError("Gemini Down"))
    router = LLMRouter(groq_client=mock_groq_client, gemini_client=mock_gemini_client)

    messages = [LLMMessage(role="user", content="Explain pulpitis.")]
    with pytest.raises(RuntimeError):
        await router.execute_with_fallback(
            task_type=TaskType.TUTOR,
            messages=messages,
            complexity=ComplexityLevel.LOW,
        )
