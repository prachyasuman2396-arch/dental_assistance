import json
import time
from typing import Optional, Dict, Any, List, AsyncGenerator
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.db.repositories.conversation_repo import ConversationRepository
from app.db.repositories.profile_repo import ProfileRepository
from app.db.repositories.memory_repo import MemoryRepository
from app.api.dependencies import get_current_user
from app.db.models.user import User
from app.llm.router import LLMRouter
from app.llm.schemas import TaskType, ComplexityLevel, LLMMessage
from app.research.service import ResearchService
from app.rag.hybrid import HybridRetriever
from app.rag.vector_store import PgVectorRetriever
from app.prompts.tutor import DENTAL_TUTOR_SYSTEM_PROMPT
from app.prompts.research import RESEARCH_SYNTHESIS_SYSTEM_PROMPT
from app.prompts.study import QUIZ_GENERATION_PROMPT, FLASHCARD_GENERATION_PROMPT
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
        initial_title = req.message[:50].strip() or "Study Session"
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

    # 4. Construct tools & nodes
    router_instance = LLMRouter()
    research_svc = ResearchService()
    retriever_factory = lambda: HybridRetriever(session=session)
    profile_repo_factory = lambda: ProfileRepository(session)
    memory_repo_factory = lambda: MemoryRepository(session)

    nodes = DentalGraphNodes(
        router=router_instance,
        research_service=research_svc,
        retriever_factory=retriever_factory,
        profile_repo_factory=profile_repo_factory,
        memory_repo_factory=memory_repo_factory,
    )

    # 5. Handle True Real-Time SSE Streaming if requested
    if req.stream:
        async def event_generator() -> AsyncGenerator[str, None]:
            full_answer_parts: List[str] = []
            selected_provider = "groq"
            selected_model = "unknown"
            citations_meta: Dict[str, List[Dict[str, Any]]] = {
                "documents": [],
                "research_papers": [],
            }

            try:
                # 5a. message_start event
                start_payload = json.dumps({
                    "type": "message_start",
                    "conversation_id": conversation_id,
                })
                yield f"event: message_start\ndata: {start_payload}\n\n"

                # 5b. status event: context loading
                yield f"event: status\ndata: {json.dumps({'type': 'status', 'status': 'loading_context', 'message': 'Loading study profile and context...'})}\n\n"

                p_repo = ProfileRepository(session)
                m_repo = MemoryRepository(session)

                profile_data: Dict[str, Any] = {}
                try:
                    p_obj = await p_repo.get_by_user_id(current_user.id)
                    if p_obj and hasattr(p_obj, "preferred_name") and not hasattr(p_obj.preferred_name, "__await__"):
                        profile_data = {
                            "preferred_name": p_obj.preferred_name,
                            "academic_discipline": p_obj.academic_discipline,
                            "current_level": p_obj.current_level,
                            "explanation_style": p_obj.explanation_style,
                            "learning_goals": p_obj.learning_goals or [],
                        }
                except Exception as pe:
                    logger.debug(f"Could not load user profile in streaming: {pe}")

                memories_data: List[Dict[str, Any]] = []
                try:
                    memories_objs = await m_repo.search_memories(
                        user_id=current_user.id, query=req.message, limit=5
                    )
                    if isinstance(memories_objs, list):
                        memories_data = [
                            {
                                "topic": getattr(m, "topic", ""),
                                "content": getattr(m, "content", ""),
                                "memory_type": getattr(m, "memory_type", ""),
                            }
                            for m in memories_objs
                            if hasattr(m, "content") and not hasattr(getattr(m, "content"), "__await__")
                        ]
                except Exception as me:
                    logger.debug(f"Could not search memories in streaming: {me}")

                # 5c. status event: classification
                yield f"event: status\ndata: {json.dumps({'type': 'status', 'status': 'classifying', 'message': 'Analyzing query intent and complexity...'})}\n\n"

                state: AgentState = {
                    "messages": history_messages,
                    "user_id": current_user.id,
                    "conversation_id": conversation_id,
                    "document_id": req.document_id,
                    "profile": profile_data,
                    "long_term_memories": memories_data,
                    "retry_count": 0,
                    "citations": {},
                    "retrieved_chunks": [],
                    "research_sources": [],
                }

                classification = await nodes.classify_query(state)
                intent = classification.get("intent", "tutor")
                complexity_str = classification.get("task_complexity", "low")
                complexity = (
                    ComplexityLevel.HIGH
                    if complexity_str == "high"
                    else (
                        ComplexityLevel.MEDIUM
                        if complexity_str == "medium"
                        else ComplexityLevel.LOW
                    )
                )
                search_query = classification.get("search_query") or req.message
                state["intent"] = intent
                state["task_complexity"] = complexity_str
                state["search_query"] = search_query

                # 5d. Retrieve evidence if needed
                chunks = []
                sources = []
                if intent == "document_retrieval":
                    yield f"event: status\ndata: {json.dumps({'type': 'status', 'status': 'retrieving', 'message': 'Searching uploaded course materials...'})}\n\n"
                    doc_res = await nodes.document_retrieval(state)
                    chunks = doc_res.get("retrieved_chunks", [])
                    state["retrieved_chunks"] = chunks
                elif intent == "web_research":
                    yield f"event: status\ndata: {json.dumps({'type': 'status', 'status': 'searching', 'message': 'Searching scholarly databases...'})}\n\n"
                    web_res = await nodes.web_research(state)
                    sources = web_res.get("research_sources", [])
                    state["research_sources"] = sources
                elif intent == "hybrid_retrieval":
                    yield f"event: status\ndata: {json.dumps({'type': 'status', 'status': 'hybrid_search', 'message': 'Searching documents and research databases...'})}\n\n"
                    hybrid_res = await nodes.hybrid_retrieval(state)
                    chunks = hybrid_res.get("retrieved_chunks", [])
                    sources = hybrid_res.get("research_sources", [])
                    state["retrieved_chunks"] = chunks
                    state["research_sources"] = sources

                # 5e. Format citations
                if chunks:
                    for c in chunks:
                        citations_meta["documents"].append({
                            "filename": c.get("filename"),
                            "page_number": c.get("page_number"),
                            "chunk_id": c.get("chunk_id"),
                            "similarity_score": c.get("similarity_score"),
                        })
                if sources:
                    for s in sources:
                        citations_meta["research_papers"].append({
                            "title": s.get("title"),
                            "authors": s.get("authors"),
                            "journal": s.get("journal"),
                            "pub_date": s.get("publication_date"),
                            "pmid": s.get("pmid"),
                            "doi": s.get("doi"),
                            "url": s.get("url"),
                            "evidence_level": s.get("evidence_level"),
                        })

                if citations_meta["documents"] or citations_meta["research_papers"]:
                    yield f"event: citation\ndata: {json.dumps({'type': 'citation', 'citations': citations_meta})}\n\n"

                # 5f. Build LLM prompt messages
                if intent in ("document_retrieval", "web_research", "hybrid_retrieval"):
                    task_type = TaskType.RESEARCH_SYNTHESIS
                    evidence_lines = []
                    if chunks:
                        evidence_lines.append("=== UPLOADED STUDY MATERIAL / DOCUMENT EXCERPTS ===")
                        for c in chunks:
                            evidence_lines.append(
                                f"Source [{c.get('filename')}, Page {c.get('page_number')}]:\n{c.get('content')}\n"
                            )
                    if sources:
                        evidence_lines.append("=== SCHOLARLY RESEARCH & GUIDELINES ===")
                        for s in sources:
                            evidence_lines.append(
                                f"Paper: {s.get('title')}\n"
                                f"Authors: {s.get('authors')}\n"
                                f"Journal: {s.get('journal')} ({s.get('publication_date')})\n"
                                f"Abstract: {s.get('abstract') or 'No abstract available.'}\n"
                            )
                    evidence_text = "\n".join(evidence_lines)
                    prompt_msgs = [
                        LLMMessage(role="system", content=RESEARCH_SYNTHESIS_SYSTEM_PROMPT),
                        LLMMessage(
                            role="user",
                            content=(
                                f"Student Question: {req.message}\n\n"
                                f"EVIDENCE DOSSIER:\n{evidence_text}\n\n"
                                f"Please provide an accurate, step-by-step educational answer strictly supported by the evidence above."
                            ),
                        ),
                    ]
                    context_len = len(evidence_text)
                    temp = 0.4
                elif intent == "study_tools":
                    task_type = TaskType.STUDY_GENERATION
                    is_quiz = any(
                        w in req.message.lower()
                        for w in ["quiz", "mcq", "multiple choice", "test"]
                    )
                    system_prompt = (
                        QUIZ_GENERATION_PROMPT if is_quiz else FLASHCARD_GENERATION_PROMPT
                    )
                    prompt_msgs = [
                        LLMMessage(role="system", content=system_prompt),
                        LLMMessage(role="user", content=f"Topic or Request: {req.message}"),
                    ]
                    context_len = 0
                    temp = 0.4
                else:  # tutor
                    task_type = TaskType.TUTOR
                    system_content = DENTAL_TUTOR_SYSTEM_PROMPT
                    profile_parts = []
                    if profile_data.get("preferred_name"):
                        profile_parts.append(f"- Preferred Name: {profile_data['preferred_name']}")
                    if profile_data.get("academic_discipline"):
                        profile_parts.append(
                            f"- Discipline: {profile_data['academic_discipline']}"
                        )
                    if profile_data.get("current_level"):
                        profile_parts.append(f"- Study Level: {profile_data['current_level']}")
                    if profile_data.get("explanation_style"):
                        profile_parts.append(
                            f"- Explanation Preference: {profile_data['explanation_style']}"
                        )
                    if profile_data.get("learning_goals"):
                        profile_parts.append(
                            f"- Target Learning Goals: {', '.join(profile_data['learning_goals'])}"
                        )

                    memory_parts = [
                        f"- {m.get('topic') or 'Context'}: {m.get('content')}"
                        for m in memories_data[:4]
                    ]
                    additional_context = ""
                    if profile_parts:
                        additional_context += "\n\n### STUDENT PROFILE & PREFERENCES\n" + "\n".join(
                            profile_parts
                        )
                    if memory_parts:
                        additional_context += (
                            "\n\n### RELEVANT LONG-TERM STUDY MEMORY\n" + "\n".join(memory_parts)
                        )

                    prompt_msgs = [
                        LLMMessage(role="system", content=system_content + additional_context)
                    ]
                    for m in history_messages[-6:]:
                        prompt_msgs.append(
                            LLMMessage(role=m.get("role", "user"), content=m.get("content", ""))
                        )
                    context_len = 0
                    temp = 0.6

                yield f"event: status\ndata: {json.dumps({'type': 'status', 'status': 'generating', 'message': 'Generating response...'})}\n\n"

                # 5g. Live LLM token streaming
                async for chunk in router_instance.stream_with_fallback(
                    task_type=task_type,
                    messages=prompt_msgs,
                    complexity=complexity,
                    context_length=context_len,
                    temperature=temp,
                ):
                    tok = chunk.get("token", "")
                    full_answer_parts.append(tok)
                    selected_provider = chunk.get("provider", selected_provider)
                    selected_model = chunk.get("model", selected_model)
                    token_payload = json.dumps({
                        "type": "token",
                        "token": tok,
                        "provider": selected_provider,
                        "model": selected_model,
                    })
                    yield f"event: token\ndata: {token_payload}\n\n"

                full_answer = "".join(full_answer_parts)
                if intent in ("document_retrieval", "web_research", "hybrid_retrieval"):
                    if not chunks and not sources:
                        full_answer = (
                            "**Evidence Limitation Notice:**\n"
                            "No relevant passages were found in your uploaded documents or peer-reviewed queries for this specific search.\n\n"
                            + full_answer
                        )

                latency_ms = (time.perf_counter() - start_time) * 1000.0

                # 5h. Persist assistant response exactly once
                await conv_repo.add_message(
                    conversation_id=conversation_id,
                    role="assistant",
                    content=full_answer,
                    provider=selected_provider,
                    model=selected_model,
                    latency_ms=latency_ms,
                    citations=citations_meta,
                )

                # 5i. Trigger long-term memory extraction hook
                state["answer"] = full_answer
                await nodes.save_turn(state)

                # 5j. message_end event
                end_payload = json.dumps({
                    "type": "message_end",
                    "conversation_id": conversation_id,
                    "answer": full_answer,
                    "provider": selected_provider,
                    "model": selected_model,
                    "latency_ms": round(latency_ms, 2),
                    "citations": citations_meta,
                })
                yield f"event: message_end\ndata: {end_payload}\n\n"

            except Exception as e:
                logger.error(f"Streaming error in chat endpoint: {e}", exc_info=True)
                yield f"event: error\ndata: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    # 6. Non-streaming LangGraph workflow
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

    # Persist assistant turn exactly once
    await conv_repo.add_message(
        conversation_id=conversation_id,
        role="assistant",
        content=answer,
        provider=provider,
        model=model,
        latency_ms=latency_ms,
        citations=citations,
    )

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
