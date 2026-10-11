import pytest
from unittest.mock import AsyncMock, MagicMock
from app.graph.state import AgentState
from app.graph.nodes import DentalGraphNodes
from app.graph.routing import route_by_intent
from app.graph.workflow import create_dental_graph
from app.llm.schemas import LLMResponse, ProviderName
from app.research.schemas import ResearchArticle, EvidenceLevel
from app.rag.vector_store import RetrievedChunk


@pytest.mark.asyncio
async def test_classify_query_routes_conceptual_to_tutor(mock_router):
    # Mock classifier output
    mock_router.execute_with_fallback = AsyncMock(
        return_value=LLMResponse(
            content='{"intent": "tutor", "complexity": "low", "search_query": "amelogenesis", "reasoning": "conceptual definition"}',
            provider=ProviderName.GROQ,
            model="llama-3.1-8b-instant",
        )
    )
    research_mock = AsyncMock()
    nodes = DentalGraphNodes(router=mock_router, research_service=research_mock)

    state: AgentState = {
        "messages": [{"role": "user", "content": "Explain the stages of amelogenesis."}],
    }

    result = await nodes.classify_query(state)
    assert result["intent"] == "tutor"
    assert result["task_complexity"] == "low"


@pytest.mark.asyncio
async def test_classify_query_routes_document_when_document_id_present(mock_router):
    research_mock = AsyncMock()
    nodes = DentalGraphNodes(router=mock_router, research_service=research_mock)

    state: AgentState = {
        "messages": [{"role": "user", "content": "What does chapter 3 of the uploaded textbook say about apexification?"}],
        "document_id": "doc-uuid-12345",
    }

    result = await nodes.classify_query(state)
    assert result["intent"] == "document_retrieval"


@pytest.mark.asyncio
async def test_end_to_end_graph_execution_tutor_flow(mock_router):
    # Setup mock router to handle classification then tutor response
    async def mock_execute(*args, **kwargs):
        task_type = kwargs.get("task_type")
        if task_type == "classification":
            return LLMResponse(
                content='{"intent": "tutor", "complexity": "low"}',
                provider=ProviderName.GROQ,
                model="llama-3.1-8b-instant",
            )
        return LLMResponse(
            content="Reversible pulpitis is characterized by quick, non-lingering pain to thermal stimuli.",
            provider=ProviderName.GROQ,
            model="llama-3.3-70b-versatile",
        )

    mock_router.execute_with_fallback = AsyncMock(side_effect=mock_execute)
    research_mock = AsyncMock()

    nodes = DentalGraphNodes(router=mock_router, research_service=research_mock)
    graph = create_dental_graph(nodes)

    initial_state: AgentState = {
        "messages": [{"role": "user", "content": "What is reversible pulpitis?"}],
        "user_id": "student-1",
        "conversation_id": "conv-1",
    }

    final_state = await graph.ainvoke(initial_state)
    assert "Reversible pulpitis" in final_state["answer"]
    assert final_state["intent"] == "tutor"
    assert final_state["selected_provider"] == "groq"
