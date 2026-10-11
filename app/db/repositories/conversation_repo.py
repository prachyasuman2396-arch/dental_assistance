from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from app.db.models.conversation import Conversation
from app.db.models.message import Message


class ConversationRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, user_id: str, title: str = "New Study Session", metadata_json: Optional[dict] = None) -> Conversation:
        conv = Conversation(
            user_id=user_id,
            title=title,
            metadata_json=metadata_json or {},
        )
        self.session.add(conv)
        await self.session.commit()
        await self.session.refresh(conv)
        return conv

    async def get_by_id(self, conversation_id: str, user_id: str) -> Optional[Conversation]:
        """Fetch conversation enforcing user tenancy."""
        stmt = select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.user_id == user_id,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_user(self, user_id: str, limit: int = 50, offset: int = 0) -> List[Conversation]:
        stmt = (
            select(Conversation)
            .where(Conversation.user_id == user_id)
            .order_by(desc(Conversation.updated_at))
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def delete(self, conversation_id: str, user_id: str) -> bool:
        conv = await self.get_by_id(conversation_id, user_id)
        if not conv:
            return False
        await self.session.delete(conv)
        await self.session.commit()
        return True

    async def add_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        tokens_used: Optional[int] = None,
        latency_ms: Optional[float] = None,
        citations: Optional[dict] = None,
    ) -> Message:
        msg = Message(
            conversation_id=conversation_id,
            role=role,
            content=content,
            provider=provider,
            model=model,
            tokens_used=tokens_used,
            latency_ms=latency_ms,
            citations=citations or {},
        )
        self.session.add(msg)
        await self.session.commit()
        await self.session.refresh(msg)
        return msg

    async def get_messages(self, conversation_id: str, user_id: str) -> List[Message]:
        conv = await self.get_by_id(conversation_id, user_id)
        if not conv:
            return []
        stmt = (
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.asc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
