from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from enum import Enum
from pydantic import BaseModel, Field


class MCPToolCategory(str, Enum):
    WEB_RESEARCH = "web_research"
    SCHOLARLY_RESEARCH = "scholarly_research"
    STUDY_TOOLS = "study_tools"
    APPLICATION_KNOWLEDGE = "application_knowledge"


class MCPToolSchema(BaseModel):
    name: str
    description: str
    category: MCPToolCategory
    input_schema: Dict[str, Any]
    output_schema: Optional[Dict[str, Any]] = None
    requires_auth: bool = True
    timeout_seconds: float = 30.0


class MCPToolCallRequest(BaseModel):
    tool_name: str
    arguments: Dict[str, Any] = Field(default_factory=dict)
    conversation_id: Optional[str] = None


class MCPToolResult(BaseModel):
    tool_name: str
    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None
    latency_ms: float = 0.0
    audited_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class MCPAuditLog(BaseModel):
    tool_name: str
    user_id: str
    arguments_redacted: Dict[str, Any]
    success: bool
    error: Optional[str] = None
    latency_ms: float
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
