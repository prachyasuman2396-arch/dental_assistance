from typing import List, Dict, Any, Optional
from typing_extensions import TypedDict


class AgentState(TypedDict, total=False):
    """
    Typed workflow state for the Dental AI Assistant LangGraph pipeline.
    Contains only workflow-essential, non-secret fields.
    """
    messages: List[Dict[str, Any]]
    user_id: str
    conversation_id: str
    document_id: Optional[str]
    academic_level: Optional[str]
    
    # Classification & routing
    intent: str  # tutor, web_research, document_retrieval, hybrid_retrieval, study_tools
    task_complexity: str  # low, medium, high
    search_query: Optional[str]
    
    # Provider selection telemetry
    selected_provider: Optional[str]
    selected_model: Optional[str]
    
    # Retrieved evidence
    retrieved_chunks: List[Dict[str, Any]]
    research_sources: List[Dict[str, Any]]
    
    # Synthesized output & verification
    answer: str
    citations: Dict[str, Any]
    evidence_sufficient: bool
    retry_count: int
    error: Optional[str]
