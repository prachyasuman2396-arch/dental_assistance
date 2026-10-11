from typing import Literal
from app.graph.state import AgentState


def route_by_intent(
    state: AgentState,
) -> Literal["tutor", "web_research", "document_retrieval", "hybrid_retrieval", "study_tools"]:
    intent = state.get("intent", "tutor")
    if intent in ("tutor", "web_research", "document_retrieval", "hybrid_retrieval", "study_tools"):
        return intent
    return "tutor"


def route_after_verification(
    state: AgentState,
) -> Literal["save_turn", "web_research"]:
    """
    If retrieval produced zero evidence and retry count is 0,
    retry with fallback research once; otherwise conclude.
    """
    evidence_sufficient = state.get("evidence_sufficient", True)
    retry_count = state.get("retry_count", 0)
    intent = state.get("intent", "tutor")

    if not evidence_sufficient and retry_count < 1 and intent in ("document_retrieval", "web_research"):
        return "web_research"

    return "save_turn"
