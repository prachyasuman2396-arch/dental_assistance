from typing import Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.models.profile import UserProfile
from app.core.logging import logger


class ProfileRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_user_id(self, user_id: str) -> Optional[UserProfile]:
        """Fetch user profile by user_id."""
        stmt = select(UserProfile).where(UserProfile.user_id == user_id)
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def create_or_update(
        self,
        user_id: str,
        preferred_name: Optional[str] = None,
        academic_institution: Optional[str] = None,
        academic_discipline: Optional[str] = None,
        current_level: Optional[str] = None,
        explanation_style: Optional[str] = None,
        learning_goals: Optional[List[str]] = None,
        preferences_json: Optional[Dict[str, Any]] = None,
    ) -> UserProfile:
        """Create or update persistent profile for a student."""
        profile = await self.get_by_user_id(user_id)
        if not profile:
            profile = UserProfile(
                user_id=user_id,
                preferred_name=preferred_name,
                academic_institution=academic_institution,
                academic_discipline=academic_discipline or "General Studies",
                current_level=current_level or "Undergraduate",
                explanation_style=explanation_style or "intuitive_first",
                learning_goals=learning_goals or [],
                preferences_json=preferences_json or {},
            )
            self.session.add(profile)
        else:
            if preferred_name is not None:
                profile.preferred_name = preferred_name
            if academic_institution is not None:
                profile.academic_institution = academic_institution
            if academic_discipline is not None:
                profile.academic_discipline = academic_discipline
            if current_level is not None:
                profile.current_level = current_level
            if explanation_style is not None:
                profile.explanation_style = explanation_style
            if learning_goals is not None:
                profile.learning_goals = learning_goals
            if preferences_json is not None:
                profile.preferences_json = preferences_json

        await self.session.commit()
        await self.session.refresh(profile)
        return profile

    async def delete(self, user_id: str) -> bool:
        """Delete profile for a student."""
        profile = await self.get_by_user_id(user_id)
        if profile:
            await self.session.delete(profile)
            await self.session.commit()
            return True
        return False
