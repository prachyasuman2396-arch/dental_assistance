import json
import re
from typing import Dict, Any, List
from app.graph.state import AgentState
from app.llm.router import LLMRouter
from app.llm.schemas import TaskType, ComplexityLevel, LLMMessage
from app.prompts.tutor import DENTAL_TUTOR_SYSTEM_PROMPT
from app.prompts.classifier import CLASSIFICATION_SYSTEM_PROMPT
from app.prompts.research import RESEARCH_SYNTHESIS_SYSTEM_PROMPT
from app.prompts.study import QUIZ_GENERATION_PROMPT, FLASHCARD_GENERATION_PROMPT
from app.research.service import ResearchService
from app.rag.vector_store import PgVectorRetriever
from app.rag.hybrid import HybridRetriever
from app.core.logging import logger


class DentalGraphNodes:
    def __init__(
        self,
        router: LLMRouter,
        research_service: ResearchService,
        retriever_factory=None,  # callable that receives async session
        profile_repo_factory=None,
        memory_repo_factory=None,
    ):
        self.router = router
        self.research = research_service
        self.retriever_factory = retriever_factory
        self.profile_repo_factory = profile_repo_factory
        self.memory_repo_factory = memory_repo_factory

    async def load_context(self, state: AgentState) -> Dict[str, Any]:
        """Validate input state, restore user profile, and fetch relevant long-term memories."""
        messages = state.get("messages", [])
        retry_count = state.get("retry_count", 0)
        user_id = state.get("user_id", "")
        last_query = messages[-1].get("content", "") if messages else ""

        profile_data = state.get("profile")
        if not profile_data and self.profile_repo_factory and user_id:
            try:
                p_repo = self.profile_repo_factory()
                p_obj = await p_repo.get_by_user_id(user_id)
                if p_obj:
                    profile_data = {
                        "preferred_name": p_obj.preferred_name,
                        "academic_discipline": p_obj.academic_discipline,
                        "current_level": p_obj.current_level,
                        "explanation_style": p_obj.explanation_style,
                        "learning_goals": p_obj.learning_goals or [],
                    }
            except Exception as e:
                logger.warning(f"Error loading profile in graph: {e}")

        memories_data = state.get("long_term_memories", [])
        if not memories_data and self.memory_repo_factory and user_id and last_query:
            try:
                m_repo = self.memory_repo_factory()
                m_objs = await m_repo.search_memories(user_id=user_id, query=last_query, limit=5)
                memories_data = [
                    {"topic": m.topic, "content": m.content, "memory_type": m.memory_type}
                    for m in m_objs
                ]
            except Exception as e:
                logger.warning(f"Error searching long-term memories in graph: {e}")

        return {
            "retry_count": retry_count,
            "evidence_sufficient": True,
            "profile": profile_data,
            "long_term_memories": memories_data,
            "citations": state.get("citations", {}),
            "retrieved_chunks": state.get("retrieved_chunks", []),
            "research_sources": state.get("research_sources", []),
        }

    async def classify_query(self, state: AgentState) -> Dict[str, Any]:
        """Classify user query intent and complexity."""
        messages = state.get("messages", [])
        if not messages:
            return {"intent": "tutor", "task_complexity": "low"}

        last_user_msg = messages[-1].get("content", "")
        document_id = state.get("document_id")

        # If user explicitly references uploaded document or document_id is provided
        if document_id and any(w in last_user_msg.lower() for w in ["document", "pdf", "textbook", "page", "slide", "chapter"]):
            return {
                "intent": "document_retrieval",
                "task_complexity": "medium",
                "search_query": last_user_msg,
            }

        # Prompt LLM classifier
        prompt_msgs = [
            LLMMessage(role="system", content=CLASSIFICATION_SYSTEM_PROMPT),
            LLMMessage(role="user", content=f"User Query: {last_user_msg}"),
        ]

        try:
            res = await self.router.execute_with_fallback(
                task_type=TaskType.CLASSIFICATION,
                messages=prompt_msgs,
                complexity=ComplexityLevel.LOW,
                temperature=0.1,
                max_tokens=250,
            )

            # Parse JSON
            raw_content = res.content.strip()
            # Remove Markdown block if present
            raw_content = re.sub(r"^```json\s*", "", raw_content)
            raw_content = re.sub(r"\s*```$", "", raw_content)
            parsed = json.loads(raw_content)

            intent = parsed.get("intent", "tutor")
            complexity = parsed.get("complexity", "low")
            search_query = parsed.get("search_query") or last_user_msg

            # If document_id was provided and query is conceptual, consider if user wants doc retrieval
            if document_id and intent == "tutor":
                intent = "document_retrieval"

            return {
                "intent": intent,
                "task_complexity": complexity,
                "search_query": search_query,
                "selected_provider": res.provider.value,
                "selected_model": res.model,
            }

        except Exception as e:
            logger.warning(f"Classification parse failed ({e}), using heuristic classification.")
            low_query = last_user_msg.lower()
            if any(k in low_query for k in ["mcq", "quiz", "flashcard", "viva", "exam questions"]):
                intent = "study_tools"
            elif any(k in low_query for k in ["research", "pubmed", "trial", "guideline", "meta-analysis", "study"]):
                intent = "web_research"
            elif document_id:
                intent = "document_retrieval"
            else:
                intent = "tutor"

            return {
                "intent": intent,
                "task_complexity": "low",
                "search_query": last_user_msg,
            }

    async def tutor(self, state: AgentState) -> Dict[str, Any]:
        """Direct pedagogical student tutor response with profile and long-term memory integration."""
        messages = state.get("messages", [])
        complexity_str = state.get("task_complexity", "low")
        complexity = (
            ComplexityLevel.HIGH
            if complexity_str == "high"
            else (ComplexityLevel.MEDIUM if complexity_str == "medium" else ComplexityLevel.LOW)
        )

        system_content = DENTAL_TUTOR_SYSTEM_PROMPT
        profile = state.get("profile") or {}
        memories = state.get("long_term_memories") or []

        profile_parts = []
        if profile.get("preferred_name"):
            profile_parts.append(f"- Preferred Name: {profile['preferred_name']}")
        if profile.get("academic_discipline"):
            profile_parts.append(f"- Discipline: {profile['academic_discipline']}")
        if profile.get("current_level"):
            profile_parts.append(f"- Study Level: {profile['current_level']}")
        if profile.get("explanation_style"):
            profile_parts.append(f"- Explanation Preference: {profile['explanation_style']}")
        if profile.get("learning_goals"):
            profile_parts.append(f"- Target Learning Goals: {', '.join(profile['learning_goals'])}")

        memory_parts = [f"- {m.get('topic') or 'Context'}: {m.get('content')}" for m in memories[:4]]

        additional_context = ""
        if profile_parts:
            additional_context += "\n\n### STUDENT PROFILE & PREFERENCES\n" + "\n".join(profile_parts)
        if memory_parts:
            additional_context += "\n\n### RELEVANT LONG-TERM STUDY MEMORY\n" + "\n".join(memory_parts)

        llm_messages = [LLMMessage(role="system", content=system_content + additional_context)]
        # Pass conversation history (last 6 turns)
        for m in messages[-6:]:
            llm_messages.append(LLMMessage(role=m.get("role", "user"), content=m.get("content", "")))

        res = await self.router.execute_with_fallback(
            task_type=TaskType.TUTOR,
            messages=llm_messages,
            complexity=complexity,
            temperature=0.6,
        )

        return {
            "answer": res.content,
            "selected_provider": res.provider.value,
            "selected_model": res.model,
            "citations": {},
        }

    async def document_retrieval(self, state: AgentState) -> Dict[str, Any]:
        """Retrieve relevant textbook/PDF chunks with pgvector or hybrid retriever."""
        query = state.get("search_query") or state.get("messages", [{}])[-1].get("content", "")
        user_id = state.get("user_id", "")
        document_id = state.get("document_id")

        chunks = []
        is_sufficient = True
        if self.retriever_factory:
            retriever = self.retriever_factory()
            if hasattr(retriever, "pipeline_retrieve"):
                chunks, _metrics, evaluation = await retriever.pipeline_retrieve(
                    query=query,
                    user_id=user_id,
                    document_id=document_id,
                    top_k=5,
                )
                is_sufficient = evaluation.is_sufficient
            elif hasattr(retriever, "retrieve"):
                chunks = await retriever.retrieve(
                    query=query,
                    user_id=user_id,
                    document_id=document_id,
                    top_k=5,
                )
                is_sufficient = len(chunks) > 0
            elif hasattr(retriever, "similarity_search"):
                chunks = await retriever.similarity_search(
                    query=query,
                    user_id=user_id,
                    document_id=document_id,
                    top_k=5,
                )
                is_sufficient = len(chunks) > 0

        serialized_chunks = [c.model_dump() for c in chunks]
        return {
            "retrieved_chunks": serialized_chunks,
            "evidence_sufficient": is_sufficient and len(serialized_chunks) > 0,
        }

    async def web_research(self, state: AgentState) -> Dict[str, Any]:
        """Search PubMed and scholarly biomedical databases."""
        query = state.get("search_query") or state.get("messages", [{}])[-1].get("content", "")
        articles = await self.research.search_literature(query=query, max_results=5)
        serialized_articles = [a.model_dump() for a in articles]

        return {
            "research_sources": serialized_articles,
            "evidence_sufficient": len(serialized_articles) > 0,
        }

    async def hybrid_retrieval(self, state: AgentState) -> Dict[str, Any]:
        """Simultaneous document and scholarly literature retrieval."""
        doc_res = await self.document_retrieval(state)
        web_res = await self.web_research(state)
        return {
            "retrieved_chunks": doc_res.get("retrieved_chunks", []),
            "research_sources": web_res.get("research_sources", []),
            "evidence_sufficient": (
                len(doc_res.get("retrieved_chunks", [])) > 0
                or len(web_res.get("research_sources", [])) > 0
            ),
        }

    async def study_tools(self, state: AgentState) -> Dict[str, Any]:
        """Generate MCQs, flashcards, or viva questions."""
        messages = state.get("messages", [])
        last_user_msg = messages[-1].get("content", "") if messages else ""

        is_quiz = any(w in last_user_msg.lower() for w in ["quiz", "mcq", "multiple choice", "test"])
        system_prompt = QUIZ_GENERATION_PROMPT if is_quiz else FLASHCARD_GENERATION_PROMPT

        llm_messages = [
            LLMMessage(role="system", content=system_prompt),
            LLMMessage(role="user", content=f"Topic or Request: {last_user_msg}"),
        ]

        res = await self.router.execute_with_fallback(
            task_type=TaskType.STUDY_GENERATION,
            messages=llm_messages,
            complexity=ComplexityLevel.LOW,
            temperature=0.4,
        )

        return {
            "answer": res.content,
            "selected_provider": res.provider.value,
            "selected_model": res.model,
            "citations": {},
        }

    async def synthesize(self, state: AgentState) -> Dict[str, Any]:
        """Synthesize answers grounded in document chunks and research papers."""
        messages = state.get("messages", [])
        user_query = messages[-1].get("content", "") if messages else ""
        chunks = state.get("retrieved_chunks", [])
        sources = state.get("research_sources", [])

        # Build evidence context block
        evidence_lines = []
        citations_meta = {"documents": [], "research_papers": []}

        if chunks:
            evidence_lines.append("=== UPLOADED TEXTBOOK / DOCUMENT EVIDENCE ===")
            for c in chunks:
                ref_id = f"[{c.get('filename')}, Page {c.get('page_number')}]"
                evidence_lines.append(f"Source {ref_id}:\n{c.get('content')}\n")
                citations_meta["documents"].append({
                    "filename": c.get("filename"),
                    "page_number": c.get("page_number"),
                    "chunk_id": c.get("chunk_id"),
                    "similarity_score": c.get("similarity_score"),
                })

        if sources:
            evidence_lines.append("=== SCHOLARLY RESEARCH & GUIDELINES ===")
            for s in sources:
                ref_id = f"({s.get('title')} - PMID: {s.get('pmid') or 'N/A'}, DOI: {s.get('doi') or 'N/A'})"
                evidence_lines.append(
                    f"Paper: {s.get('title')}\n"
                    f"Authors: {s.get('authors')}\n"
                    f"Journal: {s.get('journal')} ({s.get('publication_date')})\n"
                    f"Evidence Level: {s.get('evidence_level')}\n"
                    f"Abstract/Summary: {s.get('abstract') or 'Abstract not indexed in summary.'}\n"
                )
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

        evidence_text = "\n".join(evidence_lines)

        llm_messages = [
            LLMMessage(role="system", content=RESEARCH_SYNTHESIS_SYSTEM_PROMPT),
            LLMMessage(
                role="user",
                content=(
                    f"Student Question: {user_query}\n\n"
                    f"EVIDENCE DOSSIER:\n{evidence_text}\n\n"
                    f"Please provide an accurate, step-by-step educational answer strictly supported by the evidence above."
                ),
            ),
        ]

        res = await self.router.execute_with_fallback(
            task_type=TaskType.RESEARCH_SYNTHESIS,
            messages=llm_messages,
            complexity=ComplexityLevel.HIGH,
            context_length=len(evidence_text),
            temperature=0.4,
        )

        return {
            "answer": res.content,
            "citations": citations_meta,
            "selected_provider": res.provider.value,
            "selected_model": res.model,
        }

    async def verify_answer(self, state: AgentState) -> Dict[str, Any]:
        """
        Verify factual citation alignment. If retrieved evidence was empty,
        ensure an honest limitation message is appended instead of hallucinating.
        """
        answer = state.get("answer", "")
        intent = state.get("intent", "tutor")
        chunks = state.get("retrieved_chunks", [])
        sources = state.get("research_sources", [])

        if intent in ("document_retrieval", "web_research", "hybrid_retrieval"):
            if not chunks and not sources:
                answer = (
                    "**Evidence Limitation Notice:**\n"
                    "No relevant passages were found in your uploaded documents or peer-reviewed queries for this specific search.\n\n"
                    + answer
                )

        return {"answer": answer}

    async def save_turn(self, state: AgentState) -> Dict[str, Any]:
        """Final state persistence and automated memory extraction hook."""
        user_id = state.get("user_id")
        messages = state.get("messages", [])
        last_msg = messages[-1].get("content", "") if messages else ""
        extracted = []

        if self.memory_repo_factory and user_id and last_msg:
            lower_msg = last_msg.lower()
            if any(k in lower_msg for k in ["remember this", "save this topic", "add to my goals", "my goal is", "i want to learn", "revision list"]):
                try:
                    m_repo = self.memory_repo_factory()
                    mem = await m_repo.add_memory(
                        user_id=user_id,
                        memory_type="study_goal" if "goal" in lower_msg else "saved_topic",
                        content=last_msg,
                        topic=state.get("search_query") or "General Study",
                        importance=2,
                    )
                    extracted.append({"id": mem.id, "content": mem.content, "type": mem.memory_type})
                except Exception as e:
                    logger.warning(f"Error persisting extracted memory: {e}")

        state["extracted_memories"] = extracted
        return state



# Alias for general academic graph nodes
StudyGraphNodes = DentalGraphNodes

