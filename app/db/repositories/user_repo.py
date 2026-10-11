from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.models.user import User
from app.core.security import get_password_hash


class UserRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, user_id: str) -> Optional[User]:
        stmt = select(User).where(User.id == user_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> Optional[User]:
        stmt = select(User).where(User.email == email.lower())
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def create(
        self,
        email: str,
        password: str,
        full_name: Optional[str] = None,
        academic_level: str = "Dental Student",
    ) -> User:
        user = User(
            email=email.lower().strip(),
            hashed_password=get_password_hash(password),
            full_name=full_name,
            academic_level=academic_level,
        )
        self.session.add(user)
        await self.session.commit()
        await self.session.refresh(user)
        return user
