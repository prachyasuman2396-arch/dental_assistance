import json
import time
from typing import Optional, Dict, Any, List
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.db.repositories.conversation_repo import ConversationRepository
from app.api.dependencies import get_current_user
from app.db.models.user import User
from app.llm.router import LLMRouter
from app.research.service import ResearchService
from app.rag.vector_store import PgVectorRetriever
from app.graph.nodes import DentalGraphNodes
from app.graph.workflow import create_dental_graph
from app.graph.state import AgentState
from app.core.logging import logger

router = APIRouter(prefix="/chat", tags=["Chat"])


class ChatRequest(BaseModel):
    message: str
    conversation_id: Optional[str] = None
    document_id: Optional[str] = None
    stream: bool = False


class ChatResponse(BaseModel):
    conversation_id: str
    message: str
    provider: Optional[str] = None
    model: Optional[str] = None
    latency_ms: float
    citations: Dict[str, Any]
    retrieved_chunks_count: int = 0
    research_sources_count: int = 0


@router.post("", response_model=ChatResponse)
async def chat_endpoint(
    req: ChatRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    start_time = time.perf_counter()
    conv_repo = ConversationRepository(session)

    # 1. Resolve or create conversation
    if req.conversation_id:
        conv = await conv_repo.get_by_id(req.conversation_id, current_user.id)
        if not conv:
            raise HTTPException(status_code=404, detail="Conversation not found or access denied.")
        conversation_id = conv.id
    else:
        # Generate initial title from first 50 chars of query
        initial_title = req.message[:50].strip() or "Dental Study Session"
        conv = await conv_repo.create(user_id=current_user.id, title=initial_title)
        conversation_id = conv.id

    # 2. Persist user message
    await conv_repo.add_message(
        conversation_id=conversation_id,
        role="user",
        content=req.message,
    )

    # 3. Fetch recent conversation history
    history = await conv_repo.get_messages(conversation_id, current_user.id)
    history_messages = [{"role": m.role, "content": m.content} for m in history]

    # 4. Construct LangGraph nodes & workflow
    router_instance = LLMRouter()
    research_svc = ResearchService()
    retriever_factory = lambda: PgVectorRetriever(session=session)

    nodes = DentalGraphNodes(
        router=router_instance,
        research_service=research_svc,
        retriever_factory=retriever_factory,
    )
    workflow = create_dental_graph(nodes)

    initial_state: AgentState = {
        "messages": history_messages,
        "user_id": current_user.id,
        "conversation_id": conversation_id,
        "document_id": req.document_id,
        "academic_level": current_user.academic_level,
        "retry_count": 0,
        "retrieved_chunks": [],
        "research_sources": [],
        "citations": {},
    }

    # 5. Execute LangGraph workflow
    try:
        final_state = await workflow.ainvoke(initial_state)
    except Exception as e:
        logger.error(f"Graph execution failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Assistant execution error: {str(e)}")

    answer = final_state.get("answer", "No response generated.")
    citations = final_state.get("citations", {})
    provider = final_state.get("selected_provider")
    model = final_state.get("selected_model")
    chunks = final_state.get("retrieved_chunks", [])
    sources = final_state.get("research_sources", [])

    latency_ms = (time.perf_counter() - start_time) * 1000.0

    # 6. Persist assistant turn
    await conv_repo.add_message(
        conversation_id=conversation_id,
        role="assistant",
        content=answer,
        provider=provider,
        model=model,
        latency_ms=latency_ms,
        citations=citations,
    )

    # Handle optional SSE streaming protocol
    if req.stream:
        async def event_generator():
            yield f"data: {json.dumps({'type': 'meta', 'provider': provider, 'model': model})}\n\n"
            # Stream words or chunks safely
            words = answer.split(" ")
            for i, w in enumerate(words):
                sep = " " if i < len(words) - 1 else ""
                yield f"data: {json.dumps({'type': 'chunk', 'content': w + sep})}\n\n"
            yield f"data: {json.dumps({'type': 'done', 'citations': citations, 'latency_ms': latency_ms})}\n\n"

        return StreamingResponse(event_generator(), media_type="text/event-stream")

    return ChatResponse(
        conversation_id=conversation_id,
        message=answer,
        provider=provider,
        model=model,
        latency_ms=round(latency_ms, 2),
        citations=citations,
        retrieved_chunks_count=len(chunks),
        research_sources_count=len(sources),
    )
