import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from unittest.mock import AsyncMock, MagicMock
from app.llm.base import BaseLLMClient
from app.llm.schemas import LLMResponse, ProviderName
from app.llm.router import LLMRouter


@pytest.fixture
def mock_groq_client():
    client = MagicMock(spec=BaseLLMClient)
    client.provider_name = ProviderName.GROQ
    client.is_healthy = AsyncMock(return_value=True)
    client.generate = AsyncMock(
        return_value=LLMResponse(
            content="Mocked Groq Response: Dentin bonding involves acid etching.",
            provider=ProviderName.GROQ,
            model="llama-3.3-70b-versatile",
            tokens_used=42,
            latency_ms=120.0,
            finish_reason="stop",
        )
    )
    return client


@pytest.fixture
def mock_gemini_client():
    client = MagicMock(spec=BaseLLMClient)
    client.provider_name = ProviderName.GEMINI
    client.is_healthy = AsyncMock(return_value=True)
    client.generate = AsyncMock(
        return_value=LLMResponse(
            content="Mocked Gemini Response: Systematic synthesis of dental implants.",
            provider=ProviderName.GEMINI,
            model="gemini-1.5-pro",
            tokens_used=120,
            latency_ms=450.0,
            finish_reason="STOP",
        )
    )
    return client


@pytest.fixture
def mock_router(mock_groq_client, mock_gemini_client):
    return LLMRouter(groq_client=mock_groq_client, gemini_client=mock_gemini_client)
