from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class TaskType(str, Enum):
    CLASSIFICATION = "classification"
    CONVERSATION = "conversation"
    TUTOR = "tutor"
    RESEARCH_SYNTHESIS = "research_synthesis"
    STUDY_GENERATION = "study_generation"
    VERIFICATION = "verification"
    DOCUMENT_QA = "document_qa"
    MULTIMODAL = "multimodal"


class ComplexityLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Capability(str, Enum):
    FAST_INFERENCE = "fast_inference"
    LONG_CONTEXT = "long_context"
    MULTIMODAL = "multimodal"
    RESEARCH_SYNTHESIS = "research_synthesis"
    STRUCTURED_OUTPUT = "structured_output"


class ProviderName(str, Enum):
    GROQ = "groq"
    GEMINI = "gemini"


class LLMMessage(BaseModel):
    role: str  # system, user, assistant
    content: str


class LLMResponse(BaseModel):
    content: str
    provider: ProviderName
    model: str
    tokens_used: Optional[int] = None
    latency_ms: float = 0.0
    finish_reason: Optional[str] = None
    error: Optional[str] = None


class SelectedModelInfo(BaseModel):
    provider: ProviderName
    model: str
    timeout_seconds: float
    max_retries: int
    fallback_provider: Optional[ProviderName] = None
    fallback_model: Optional[str] = None
