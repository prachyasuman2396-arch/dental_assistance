import pytest
from unittest.mock import AsyncMock
from app.llm.router import LLMRouter
from app.llm.schemas import TaskType, ComplexityLevel, ProviderName, LLMResponse, LLMMessage


def test_select_model_interface():
    router = LLMRouter()
    selected = router.select_model(
        task_type=TaskType.CLASSIFICATION,
        complexity=ComplexityLevel.LOW,
    )
    assert selected.provider == ProviderName.GROQ

    selected_gemini = router.select_model(
        task_type=TaskType.RESEARCH_SYNTHESIS,
        context_length=15000,
    )
    assert selected_gemini.provider == ProviderName.GEMINI


def test_provider_health_tracking():
    router = LLMRouter()
    assert router._provider_health["groq"] is True
    assert router._provider_health["gemini"] is True

    # Record failure on Groq
    router.record_failure("groq")
    assert router._provider_health["groq"] is False

    # Dynamic select_model falls back away from unhealthy Groq
    selected = router.select_model(
        task_type=TaskType.CLASSIFICATION,
        complexity=ComplexityLevel.LOW,
    )
    assert selected.provider == ProviderName.GEMINI

    # Record success on Groq restores health
    router.record_success("groq")
    assert router._provider_health["groq"] is True


def test_metrics_collection():
    router = LLMRouter()
    router.record_success("groq")
    router.record_success("gemini")
    router.record_failure("groq")

    metrics = router.get_metrics()
    assert metrics["total_requests"] == 2
    assert metrics["errors"] == 1
    assert metrics["provider_requests"]["groq"] == 1
    assert metrics["provider_requests"]["gemini"] == 1
    assert "provider_health" in metrics
