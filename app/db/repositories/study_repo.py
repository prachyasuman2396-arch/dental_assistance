from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from app.db.models.study import StudyCard


class StudyRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_card(
        self,
        user_id: str,
        topic: str,
        card_type: str,
        question: str,
        answer: str,
        explanation: Optional[str] = None,
        options: Optional[list] = None,
        difficulty: str = "medium",
    ) -> StudyCard:
        card = StudyCard(
            user_id=user_id,
            topic=topic,
            card_type=card_type,
            question=question,
            answer=answer,
            explanation=explanation,
            options=options or [],
            difficulty=difficulty,
        )
        self.session.add(card)
        await self.session.commit()
        await self.session.refresh(card)
        return card

    async def list_by_user(
        self,
        user_id: str,
        card_type: Optional[str] = None,
        topic: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[StudyCard]:
        query = select(StudyCard).where(StudyCard.user_id == user_id)
        if card_type:
            query = query.where(StudyCard.card_type == card_type)
        if topic:
            query = query.where(StudyCard.topic.ilike(f"%{topic}%"))
        query = query.order_by(desc(StudyCard.created_at)).limit(limit).offset(offset)
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_by_id(self, card_id: str, user_id: str) -> Optional[StudyCard]:
        stmt = select(StudyCard).where(
            StudyCard.id == card_id,
            StudyCard.user_id == user_id,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def delete(self, card_id: str, user_id: str) -> bool:
        card = await self.get_by_id(card_id, user_id)
        if not card:
            return False
        await self.session.delete(card)
        await self.session.commit()
        return True
