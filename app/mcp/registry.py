import httpx
from typing import Dict, Any, List, Optional, Callable, Awaitable
from sqlalchemy.ext.asyncio import AsyncSession
from app.mcp.schemas import MCPToolSchema, MCPToolCategory
from app.mcp.security import MCPSecurityValidator
from app.research.service import ResearchService
from app.study.service import StudyService
from app.rag.hybrid import HybridRetriever
from app.db.repositories.memory_repo import MemoryRepository
from app.db.repositories.conversation_repo import ConversationRepository
from app.core.logging import logger


class MCPToolRegistry:
    """
    Standardized Model Context Protocol Tool Registry.
    Registers and dispatches modular tools across:
    1. Web Research
    2. Scholarly Research
    3. Study Tools
    4. Application Knowledge
    """
    def __init__(self):
        self._tools: Dict[str, MCPToolSchema] = {}
        self._handlers: Dict[str, Callable[..., Awaitable[Any]]] = {}
        self._register_default_tools()

    def register_tool(
        self,
        schema: MCPToolSchema,
        handler: Callable[..., Awaitable[Any]],
    ) -> None:
        self._tools[schema.name] = schema
        self._handlers[schema.name] = handler

    def list_tools(self, category: Optional[MCPToolCategory] = None) -> List[MCPToolSchema]:
        tools = list(self._tools.values())
        if category:
            tools = [t for t in tools if t.category == category]
        return tools

    def get_tool(self, tool_name: str) -> Optional[MCPToolSchema]:
        return self._tools.get(tool_name)

    async def execute_tool(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        user_id: str,
        session: AsyncSession,
        conversation_id: Optional[str] = None,
    ) -> Any:
        schema = self._tools.get(tool_name)
        if not schema:
            raise ValueError(f"Unknown MCP tool: {tool_name}")

        handler = getattr(self, f"_handle_{tool_name}", None) or self._handlers.get(tool_name)
        if not handler:
            raise NotImplementedError(f"No execution handler registered for MCP tool: {tool_name}")

        # Execute with user context and database session
        return await handler(
            arguments=arguments,
            user_id=user_id,
            session=session,
            conversation_id=conversation_id,
        )

    def _register_default_tools(self) -> None:
        # ==========================================
        # 1. WEB RESEARCH CATEGORY
        # ==========================================
        self.register_tool(
            MCPToolSchema(
                name="web_search",
                description="Search web and academic repositories for topics, news, or scientific discoveries.",
                category=MCPToolCategory.WEB_RESEARCH,
                input_schema={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "The search query"},
                        "max_results": {"type": "integer", "default": 5, "description": "Max results to return"},
                    },
                    "required": ["query"],
                },
            ),
            self._handle_web_search,
        )

        self.register_tool(
            MCPToolSchema(
                name="fetch_web_page",
                description="Fetch and extract sanitized text content from an authorized research URL.",
                category=MCPToolCategory.WEB_RESEARCH,
                input_schema={
                    "type": "object",
                    "properties": {
                        "url": {"type": "string", "description": "Public HTTP/HTTPS URL of the article or resource"}
                    },
                    "required": ["url"],
                },
            ),
            self._handle_fetch_web_page,
        )

        self.register_tool(
            MCPToolSchema(
                name="get_source_metadata",
                description="Retrieve bibliographic metadata (authors, journal, publication date, DOI) for a scholarly paper.",
                category=MCPToolCategory.WEB_RESEARCH,
                input_schema={
                    "type": "object",
                    "properties": {
                        "doi": {"type": "string", "description": "Digital Object Identifier (DOI)"}
                    },
                    "required": ["doi"],
                },
            ),
            self._handle_get_source_metadata,
        )

        # ==========================================
        # 2. SCHOLARLY RESEARCH CATEGORY
        # ==========================================
        self.register_tool(
            MCPToolSchema(
                name="pubmed_search",
                description="Search NCBI PubMed biomedical database for peer-reviewed studies, systematic reviews, and clinical guidelines.",
                category=MCPToolCategory.SCHOLARLY_RESEARCH,
                input_schema={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Biomedical / scientific search term"},
                        "max_results": {"type": "integer", "default": 5},
                    },
                    "required": ["query"],
                },
            ),
            self._handle_pubmed_search,
        )

        self.register_tool(
            MCPToolSchema(
                name="europe_pmc_search",
                description="Query Europe PMC for open-access academic articles and preprints.",
                category=MCPToolCategory.SCHOLARLY_RESEARCH,
                input_schema={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Scientific query string"},
                        "max_results": {"type": "integer", "default": 5},
                    },
                    "required": ["query"],
                },
            ),
            self._handle_europe_pmc_search,
        )

        self.register_tool(
            MCPToolSchema(
                name="crossref_metadata",
                description="Query Crossref scholarly registry for authoritative bibliographic and DOI metadata.",
                category=MCPToolCategory.SCHOLARLY_RESEARCH,
                input_schema={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Paper title or author query"},
                        "max_results": {"type": "integer", "default": 5},
                    },
                    "required": ["query"],
                },
            ),
            self._handle_crossref_metadata,
        )

        # ==========================================
        # 3. STUDY TOOLS CATEGORY
        # ==========================================
        self.register_tool(
            MCPToolSchema(
                name="generate_quiz",
                description="Generate exam-oriented multiple-choice questions (MCQs) on an academic topic.",
                category=MCPToolCategory.STUDY_TOOLS,
                input_schema={
                    "type": "object",
                    "properties": {
                        "topic": {"type": "string", "description": "Subject or concept to quiz on"},
                        "num_questions": {"type": "integer", "default": 3},
                        "difficulty": {"type": "string", "enum": ["easy", "medium", "hard"], "default": "medium"},
                    },
                    "required": ["topic"],
                },
            ),
            self._handle_generate_quiz,
        )

        self.register_tool(
            MCPToolSchema(
                name="generate_flashcards",
                description="Generate active-recall flashcards on a study topic and save to student profile.",
                category=MCPToolCategory.STUDY_TOOLS,
                input_schema={
                    "type": "object",
                    "properties": {
                        "topic": {"type": "string", "description": "Topic for flashcards"},
                        "count": {"type": "integer", "default": 4},
                        "difficulty": {"type": "string", "default": "medium"},
                    },
                    "required": ["topic"],
                },
            ),
            self._handle_generate_flashcards,
        )

        self.register_tool(
            MCPToolSchema(
                name="generate_study_plan",
                description="Generate a multi-week structured study schedule with milestones and active recall checkpoints.",
                category=MCPToolCategory.STUDY_TOOLS,
                input_schema={
                    "type": "object",
                    "properties": {
                        "subject": {"type": "string", "description": "Subject or examination to prepare for"},
                        "duration_weeks": {"type": "integer", "default": 4},
                        "target_hours_per_week": {"type": "integer", "default": 10},
                    },
                    "required": ["subject"],
                },
            ),
            self._handle_generate_study_plan,
        )

        self.register_tool(
            MCPToolSchema(
                name="generate_revision_summary",
                description="Generate a structured, high-yield summary table with key definitions, formulas, and common exam pitfalls.",
                category=MCPToolCategory.STUDY_TOOLS,
                input_schema={
                    "type": "object",
                    "properties": {
                        "topic": {"type": "string", "description": "Academic topic for revision"},
                    },
                    "required": ["topic"],
                },
            ),
            self._handle_generate_revision_summary,
        )

        self.register_tool(
            MCPToolSchema(
                name="get_study_notes",
                description="Retrieve saved study flashcards, MCQs, or revision notes for the current student.",
                category=MCPToolCategory.STUDY_TOOLS,
                input_schema={
                    "type": "object",
                    "properties": {
                        "topic": {"type": "string", "description": "Optional topic filter"},
                        "card_type": {"type": "string", "enum": ["flashcard", "mcq", "viva"], "description": "Optional card type"},
                        "limit": {"type": "integer", "default": 20},
                    },
                },
            ),
            self._handle_get_study_notes,
        )

        # ==========================================
        # 4. APPLICATION KNOWLEDGE TOOLS CATEGORY
        # ==========================================
        self.register_tool(
            MCPToolSchema(
                name="search_documents",
                description="Search the student's authorized uploaded textbooks, lecture notes, and syllabus PDFs via hybrid vector retrieval.",
                category=MCPToolCategory.APPLICATION_KNOWLEDGE,
                input_schema={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Search query into course documents"},
                        "document_id": {"type": "string", "description": "Optional document filter"},
                        "top_k": {"type": "integer", "default": 5},
                    },
                    "required": ["query"],
                },
            ),
            self._handle_search_documents,
        )

        self.register_tool(
            MCPToolSchema(
                name="search_study_memories",
                description="Search persistent cross-session study memories, saved goals, and student learning preferences.",
                category=MCPToolCategory.APPLICATION_KNOWLEDGE,
                input_schema={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Search term to find relevant memories"},
                        "limit": {"type": "integer", "default": 5},
                    },
                    "required": ["query"],
                },
            ),
            self._handle_search_study_memories,
        )

        self.register_tool(
            MCPToolSchema(
                name="get_conversation_context",
                description="Access recent conversation history turns within the active study session.",
                category=MCPToolCategory.APPLICATION_KNOWLEDGE,
                input_schema={
                    "type": "object",
                    "properties": {
                        "limit": {"type": "integer", "default": 10},
                    },
                },
            ),
            self._handle_get_conversation_context,
        )

    # ==========================================
    # TOOL EXECUTION HANDLERS
    # ==========================================
    async def _handle_web_search(self, arguments: Dict[str, Any], user_id: str, session: AsyncSession, **kwargs) -> Any:
        query = arguments.get("query", "")
        max_results = arguments.get("max_results", 5)
        service = ResearchService()
        articles = await service.search_literature(query=query, max_results=max_results)
        return [a.model_dump() for a in articles]

    async def _handle_fetch_web_page(self, arguments: Dict[str, Any], **kwargs) -> Any:
        url = arguments.get("url", "")
        if not MCPSecurityValidator.validate_url_safe(url):
            raise ValueError(f"URL violates SSRF safety policy: {url}")

        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            text = resp.text[:4000]  # bounded extract
            sanitized = MCPSecurityValidator.sanitize_output(text)
            return {"url": url, "status_code": resp.status_code, "content_snippet": sanitized}

    async def _handle_get_source_metadata(self, arguments: Dict[str, Any], **kwargs) -> Any:
        doi = arguments.get("doi", "")
        service = ResearchService()
        articles = await service.crossref.search(query=doi, max_results=1)
        if articles:
            return articles[0].model_dump()
        return {"doi": doi, "status": "not_found"}

    async def _handle_pubmed_search(self, arguments: Dict[str, Any], **kwargs) -> Any:
        query = arguments.get("query", "")
        max_results = arguments.get("max_results", 5)
        service = ResearchService()
        articles = await service.pubmed.search(query=query, max_results=max_results)
        return [a.model_dump() for a in articles]

    async def _handle_europe_pmc_search(self, arguments: Dict[str, Any], **kwargs) -> Any:
        query = arguments.get("query", "")
        max_results = arguments.get("max_results", 5)
        service = ResearchService()
        articles = await service.europe_pmc.search(query=query, max_results=max_results)
        return [a.model_dump() for a in articles]

    async def _handle_crossref_metadata(self, arguments: Dict[str, Any], **kwargs) -> Any:
        query = arguments.get("query", "")
        max_results = arguments.get("max_results", 5)
        service = ResearchService()
        articles = await service.crossref.search(query=query, max_results=max_results)
        return [a.model_dump() for a in articles]

    async def _handle_generate_quiz(self, arguments: Dict[str, Any], user_id: str, session: AsyncSession, **kwargs) -> Any:
        topic = arguments.get("topic", "")
        num_q = arguments.get("num_questions", 3)
        diff = arguments.get("difficulty", "medium")
        service = StudyService(session)
        quiz = await service.generate_quiz(user_id=user_id, topic=topic, num_questions=num_q, difficulty=diff)
        return [q.model_dump() for q in quiz]

    async def _handle_generate_flashcards(self, arguments: Dict[str, Any], user_id: str, session: AsyncSession, **kwargs) -> Any:
        topic = arguments.get("topic", "")
        count = arguments.get("count", 4)
        diff = arguments.get("difficulty", "medium")
        service = StudyService(session)
        cards = await service.generate_flashcards(user_id=user_id, topic=topic, count=count, difficulty=diff)
        return [c.model_dump() for c in cards]

    async def _handle_generate_study_plan(self, arguments: Dict[str, Any], user_id: str, session: AsyncSession, **kwargs) -> Any:
        subject = arguments.get("subject", "")
        weeks = arguments.get("duration_weeks", 4)
        hours = arguments.get("target_hours_per_week", 10)
        service = StudyService(session)
        return await service.generate_study_plan(user_id=user_id, subject=subject, duration_weeks=weeks, hours_per_week=hours)

    async def _handle_generate_revision_summary(self, arguments: Dict[str, Any], user_id: str, session: AsyncSession, **kwargs) -> Any:
        topic = arguments.get("topic", "")
        service = StudyService(session)
        return await service.generate_revision_summary(user_id=user_id, topic=topic)

    async def _handle_get_study_notes(self, arguments: Dict[str, Any], user_id: str, session: AsyncSession, **kwargs) -> Any:
        topic = arguments.get("topic")
        card_type = arguments.get("card_type")
        limit = arguments.get("limit", 20)
        service = StudyService(session)
        cards = await service.repo.list_by_user(user_id=user_id, topic=topic, card_type=card_type, limit=limit)
        return [
            {
                "id": c.id,
                "card_type": c.card_type,
                "topic": c.topic,
                "question": c.question,
                "answer": c.answer,
                "explanation": c.explanation,
                "difficulty": c.difficulty,
            }
            for c in cards
        ]

    async def _handle_search_documents(self, arguments: Dict[str, Any], user_id: str, session: AsyncSession, **kwargs) -> Any:
        query = arguments.get("query", "")
        doc_id = arguments.get("document_id")
        top_k = arguments.get("top_k", 5)
        retriever = HybridRetriever(session=session)
        chunks = await retriever.retrieve(query=query, user_id=user_id, document_id=doc_id, top_k=top_k)
        return [c.model_dump() for c in chunks]

    async def _handle_search_study_memories(self, arguments: Dict[str, Any], user_id: str, session: AsyncSession, **kwargs) -> Any:
        query = arguments.get("query", "")
        limit = arguments.get("limit", 5)
        repo = MemoryRepository(session)
        mems = await repo.search_memories(user_id=user_id, query=query, limit=limit)
        return [
            {"id": m.id, "topic": m.topic, "memory_type": m.memory_type, "content": m.content, "importance": m.importance}
            for m in mems
        ]

    async def _handle_get_conversation_context(self, arguments: Dict[str, Any], user_id: str, session: AsyncSession, conversation_id: Optional[str] = None, **kwargs) -> Any:
        if not conversation_id:
            return []
        limit = arguments.get("limit", 10)
        repo = ConversationRepository(session)
        messages = await repo.get_messages(conversation_id=conversation_id, user_id=user_id)
        return [{"role": m.role, "content": m.content, "created_at": str(m.created_at)} for m in messages[-limit:]]
