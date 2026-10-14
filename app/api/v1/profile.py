from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.api.dependencies import get_current_user
from app.db.models.user import User
from app.db.repositories.profile_repo import ProfileRepository

router = APIRouter(prefix="/profile", tags=["User Profile"])


class ProfileResponse(BaseModel):
    id: str
    user_id: str
    preferred_name: Optional[str] = None
    academic_institution: Optional[str] = None
    academic_discipline: Optional[str] = None
    current_level: Optional[str] = None
    explanation_style: Optional[str] = None
    learning_goals: List[str] = []
    preferences_json: Dict[str, Any] = {}
    created_at: str
    updated_at: str


class ProfileUpdateRequest(BaseModel):
    preferred_name: Optional[str] = None
    academic_institution: Optional[str] = None
    academic_discipline: Optional[str] = None
    current_level: Optional[str] = None
    explanation_style: Optional[str] = None
    learning_goals: Optional[List[str]] = None
    preferences_json: Optional[Dict[str, Any]] = None


@router.get("", response_model=ProfileResponse)
async def get_profile(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Retrieve the student's persistent profile (or initialize default)."""
    repo = ProfileRepository(session)
    profile = await repo.get_by_user_id(current_user.id)
    if not profile:
        profile = await repo.create_or_update(
            user_id=current_user.id,
            preferred_name=current_user.full_name,
            academic_institution=None,
            academic_discipline="General Studies",
            current_level=current_user.academic_level or "Undergraduate",
            explanation_style="intuitive_first",
            learning_goals=[],
            preferences_json={},
        )

    now_iso = datetime.now(timezone.utc).isoformat()
    return ProfileResponse(
        id=profile.id,
        user_id=profile.user_id,
        preferred_name=profile.preferred_name,
        academic_institution=profile.academic_institution,
        academic_discipline=profile.academic_discipline,
        current_level=profile.current_level,
        explanation_style=profile.explanation_style,
        learning_goals=profile.learning_goals or [],
        preferences_json=profile.preferences_json or {},
        created_at=profile.created_at.isoformat() if getattr(profile, "created_at", None) else now_iso,
        updated_at=profile.updated_at.isoformat() if getattr(profile, "updated_at", None) else now_iso,
    )


@router.put("", response_model=ProfileResponse)
async def update_profile(
    req: ProfileUpdateRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Update student profile attributes."""
    repo = ProfileRepository(session)
    profile = await repo.create_or_update(
        user_id=current_user.id,
        preferred_name=req.preferred_name,
        academic_institution=req.academic_institution,
        academic_discipline=req.academic_discipline,
        current_level=req.current_level,
        explanation_style=req.explanation_style,
        learning_goals=req.learning_goals,
        preferences_json=req.preferences_json,
    )

    now_iso = datetime.now(timezone.utc).isoformat()
    return ProfileResponse(
        id=profile.id,
        user_id=profile.user_id,
        preferred_name=profile.preferred_name,
        academic_institution=profile.academic_institution,
        academic_discipline=profile.academic_discipline,
        current_level=profile.current_level,
        explanation_style=profile.explanation_style,
        learning_goals=profile.learning_goals or [],
        preferences_json=profile.preferences_json or {},
        created_at=profile.created_at.isoformat() if getattr(profile, "created_at", None) else now_iso,
        updated_at=profile.updated_at.isoformat() if getattr(profile, "updated_at", None) else now_iso,
    )
