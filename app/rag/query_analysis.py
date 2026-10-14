import re
import json
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
from app.llm.router import LLMRouter
from app.llm.schemas import TaskType, ComplexityLevel, LLMMessage
from app.core.logging import logger


class QueryAnalysisResult(BaseModel):
    original_query: str
    standalone_query: str
    retrieval_needed: bool
    intent: str  # "tutor", "document_retrieval", "web_research", "hybrid_retrieval", "study_tools"
    sub_questions: List[str] = []
    expanded_queries: List[str] = []
    metadata_filters: Dict[str, Any] = {}
    is_ambiguous: bool = False


class QueryAnalyzer:
    """
    Advanced query understanding: contextual rewriting, intent classification,
    multi-query expansion, and sub-question decomposition.
    """
    def __init__(self, router: Optional[LLMRouter] = None):
        self.router = router or LLMRouter()

    async def analyze_and_rewrite(
        self,
        current_query: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        document_id: Optional[str] = None,
    ) -> QueryAnalysisResult:
        """
        Analyze user intent, resolve pronoun/contextual references from history,
        and generate a self-contained standalone search query.
        """
        history = conversation_history or []
        trimmed_query = current_query.strip()

        # If no conversation history, query is already standalone
        if not history:
            return QueryAnalysisResult(
                original_query=trimmed_query,
                standalone_query=trimmed_query,
                retrieval_needed=bool(document_id or self._needs_retrieval(trimmed_query)),
                intent=self._classify_heuristic(trimmed_query, document_id),
                expanded_queries=[trimmed_query],
            )

        # Contextual reference phrases to rewrite
        context_triggers = [
            "it", "this", "that", "these", "those", "explain that", "tell me more",
            "what are its", "its disadvantages", "its advantages", "compare it",
            "the previous one", "above", "as mentioned", "why is that",
        ]

        needs_rewriting = any(t in trimmed_query.lower() for t in context_triggers) or len(trimmed_query.split()) < 4

        if not needs_rewriting:
            return QueryAnalysisResult(
                original_query=trimmed_query,
                standalone_query=trimmed_query,
                retrieval_needed=bool(document_id or self._needs_retrieval(trimmed_query)),
                intent=self._classify_heuristic(trimmed_query, document_id),
                expanded_queries=[trimmed_query],
            )

        # Use LLM router to resolve context
        system_prompt = (
            "You are a pedagogical query pre-processor for an academic assistant.\n"
            "Given the recent conversation history and a follow-up question, rewrite the question "
            "into a single, complete, standalone academic search query that captures the student's true intent.\n"
            "Do NOT answer the question. Return ONLY a JSON object with keys:\n"
            '{"standalone_query": "...", "retrieval_needed": true/false, "intent": "tutor"|"document_retrieval"|"web_research"|"hybrid_retrieval"|"study_tools"}'
        )

        history_summary = "\n".join(
            f"{m.get('role', 'user').title()}: {m.get('content', '')[:150]}"
            for m in history[-4:]
        )

        user_prompt = (
            f"Recent conversation:\n{history_summary}\n\n"
            f"Student follow-up question: {trimmed_query}\n\n"
            "Generate the standalone query JSON."
        )

        try:
            res = await self.router.execute_with_fallback(
                task_type=TaskType.CLASSIFICATION,
                messages=[
                    LLMMessage(role="system", content=system_prompt),
                    LLMMessage(role="user", content=user_prompt),
                ],
                complexity=ComplexityLevel.LOW,
                temperature=0.1,
                max_tokens=200,
            )

            raw = res.content.strip()
            raw = re.sub(r"^```json\s*", "", raw)
            raw = re.sub(r"\s*```$", "", raw)
            parsed = json.loads(raw)

            standalone = parsed.get("standalone_query") or trimmed_query
            retrieval_needed = parsed.get("retrieval_needed", True)
            intent = parsed.get("intent") or self._classify_heuristic(standalone, document_id)

            return QueryAnalysisResult(
                original_query=trimmed_query,
                standalone_query=standalone,
                retrieval_needed=retrieval_needed or bool(document_id),
                intent="document_retrieval" if document_id and intent == "tutor" else intent,
                expanded_queries=[standalone],
            )

        except Exception as e:
            logger.warning(f"Contextual rewriting fallback to heuristic: {e}")
            # Heuristic resolution: append last user query topic
            last_msg = history[-1].get("content", "") if history else ""
            heuristic_standalone = f"{trimmed_query} ({last_msg[:60]})" if last_msg else trimmed_query

            return QueryAnalysisResult(
                original_query=trimmed_query,
                standalone_query=heuristic_standalone,
                retrieval_needed=bool(document_id or self._needs_retrieval(trimmed_query)),
                intent=self._classify_heuristic(trimmed_query, document_id),
                expanded_queries=[trimmed_query, heuristic_standalone],
            )

    async def generate_multi_queries(self, query: str, max_queries: int = 3) -> List[str]:
        """Generate complementary search queries covering alternative academic terminology."""
        if len(query.split()) < 4:
            return [query]

        system_prompt = (
            "You are an academic information retrieval specialist.\n"
            f"Generate up to {max_queries} diverse search query variations for the student's question.\n"
            "Use formal academic synonyms, technical nomenclature, and specific keywords.\n"
            "Return ONLY a JSON array of strings, e.g. [\"query 1\", \"query 2\"]."
        )

        try:
            res = await self.router.execute_with_fallback(
                task_type=TaskType.CLASSIFICATION,
                messages=[
                    LLMMessage(role="system", content=system_prompt),
                    LLMMessage(role="user", content=f"Target question: {query}"),
                ],
                complexity=ComplexityLevel.LOW,
                temperature=0.3,
                max_tokens=150,
            )

            raw = res.content.strip()
            raw = re.sub(r"^```json\s*", "", raw)
            raw = re.sub(r"\s*```$", "", raw)
            parsed = json.loads(raw)
            if isinstance(parsed, list) and all(isinstance(x, str) for x in parsed):
                unique_queries = [query]
                for q in parsed:
                    if q.strip() and q.strip() not in unique_queries:
                        unique_queries.append(q.strip())
                return unique_queries[:max_queries]

        except Exception as e:
            logger.debug(f"Multi-query generation skipped: {e}")

        return [query]

    async def decompose_query(self, query: str) -> List[str]:
        """Decompose compound questions (e.g. 'Compare X with Y and explain Z') into subquestions."""
        conjunctions = [" and also ", " compared to ", " versus ", " as well as ", "; "]
        if not any(c in query.lower() for c in conjunctions):
            return [query]

        system_prompt = (
            "Decompose this complex multi-part academic question into 2 or 3 distinct sub-questions.\n"
            "Return ONLY a JSON array of strings, e.g. [\"Sub-question 1\", \"Sub-question 2\"]."
        )

        try:
            res = await self.router.execute_with_fallback(
                task_type=TaskType.CLASSIFICATION,
                messages=[
                    LLMMessage(role="system", content=system_prompt),
                    LLMMessage(role="user", content=f"Question: {query}"),
                ],
                complexity=ComplexityLevel.LOW,
                temperature=0.2,
                max_tokens=200,
            )
            raw = res.content.strip()
            raw = re.sub(r"^```json\s*", "", raw)
            raw = re.sub(r"\s*```$", "", raw)
            parsed = json.loads(raw)
            if isinstance(parsed, list) and len(parsed) > 1:
                return parsed[:3]
        except Exception as e:
            logger.debug(f"Query decomposition skipped: {e}")

        return [query]

    def _needs_retrieval(self, query: str) -> bool:
        low = query.lower()
        factual_keywords = [
            "what is", "define", "explain", "how does", "mechanism", "symptoms",
            "treatment", "difference between", "formula", "cite", "source", "according to"
        ]
        return any(k in low for k in factual_keywords)

    def _classify_heuristic(self, query: str, document_id: Optional[str] = None) -> str:
        low = query.lower()
        if any(w in low for w in ["quiz", "mcq", "flashcard", "practice questions"]):
            return "study_tools"
        if any(w in low for w in ["pubmed", "clinical trial", "meta-analysis", "peer-reviewed", "journal"]):
            return "web_research"
        if document_id or any(w in low for w in ["document", "pdf", "textbook", "page", "slide"]):
            return "document_retrieval"
        return "tutor"
