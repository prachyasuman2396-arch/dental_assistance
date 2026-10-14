from typing import Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, delete
from app.db.models.memory import LongTermMemory
from app.core.logging import logger


class MemoryRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def add_memory(
        self,
        user_id: str,
        memory_type: str,
        content: str,
        topic: Optional[str] = None,
        importance: int = 1,
        metadata_json: Optional[Dict[str, Any]] = None,
    ) -> LongTermMemory:
        """
        Add or update a persistent learning memory.
        Performs deduplication: if memory of the same type and topic exists, updates content.
        """
        clean_content = content.strip()
        
        # Check deduplication by user_id, memory_type, and topic
        if topic:
            stmt = select(LongTermMemory).where(
                and_(
                    LongTermMemory.user_id == user_id,
                    LongTermMemory.memory_type == memory_type,
                    LongTermMemory.topic == topic,
                )
            )
            res = await self.session.execute(stmt)
            existing = res.scalar_one_or_none()
            if existing:
                existing.content = clean_content
                existing.importance = max(existing.importance, importance)
                if metadata_json:
                    existing.metadata_json = {**(existing.metadata_json or {}), **metadata_json}
                await self.session.commit()
                await self.session.refresh(existing)
                return existing

        mem = LongTermMemory(
            user_id=user_id,
            memory_type=memory_type,
            content=clean_content,
            topic=topic,
            importance=importance,
            metadata_json=metadata_json or {},
        )
        self.session.add(mem)
        await self.session.commit()
        await self.session.refresh(mem)
        return mem

    async def get_memories(
        self,
        user_id: str,
        memory_type: Optional[str] = None,
        limit: int = 20,
    ) -> List[LongTermMemory]:
        """Fetch user's long term learning memories ordered by importance and recency."""
        stmt = select(LongTermMemory).where(LongTermMemory.user_id == user_id)
        if memory_type:
            stmt = stmt.where(LongTermMemory.memory_type == memory_type)
        stmt = stmt.order_by(LongTermMemory.importance.desc(), LongTermMemory.updated_at.desc()).limit(limit)
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    async def search_memories(
        self,
        user_id: str,
        query: str,
        limit: int = 10,
    ) -> List[LongTermMemory]:
        """Simple keyword matching across content and topic for user's memories."""
        query_terms = [t.lower() for t in query.split() if len(t) > 2]
        all_mems = await self.get_memories(user_id=user_id, limit=50)
        if not query_terms:
            return all_mems[:limit]

        scored: List[tuple[int, LongTermMemory]] = []
        for mem in all_mems:
            text = f"{mem.topic or ''} {mem.content} {mem.memory_type}".lower()
            score = sum(1 for term in query_terms if term in text)
            if score > 0:
                scored.append((score, mem))

        scored.sort(key=lambda x: (x[0], x[1].importance), reverse=True)
        return [item[1] for item in scored[:limit]]

    async def delete_memory(self, memory_id: str, user_id: str) -> bool:
        """Delete specific memory ensuring tenant isolation."""
        stmt = delete(LongTermMemory).where(
            and_(
                LongTermMemory.id == memory_id,
                LongTermMemory.user_id == user_id,
            )
        )
        res = await self.session.execute(stmt)
        await self.session.commit()
        return res.rowcount > 0
