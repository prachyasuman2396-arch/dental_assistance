from typing import List, Optional, Dict, Any
from datetime import datetime
from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.db.repositories.study_repo import StudyRepository
from app.study.service import (
    StudyService,
    QuizQuestionItem,
    FlashcardItem,
    VivaQuestionItem,
)
from app.api.dependencies import get_current_user
from app.db.models.user import User

router = APIRouter(prefix="/study", tags=["Study Tools & Exam Prep"])


class QuizGenerateRequest(BaseModel):
    topic: str
    num_questions: int = 3
    difficulty: str = "medium"


class FlashcardGenerateRequest(BaseModel):
    topic: str
    count: int = 5
    difficulty: str = "medium"


class VivaGenerateRequest(BaseModel):
    topic: str
    count: int = 3
    difficulty: str = "medium"


class StudyPlanRequest(BaseModel):
    subject: str
    duration_weeks: int = 4
    hours_per_week: int = 10


class RevisionSummaryRequest(BaseModel):
    topic: str


class DerivationRequest(BaseModel):
    concept: str


class TopicComparisonRequest(BaseModel):
    topic_a: str
    topic_b: str


class StudyCardResponse(BaseModel):
    id: str
    card_type: str
    topic: str
    question: str
    answer: str
    explanation: Optional[str] = None
    options: Optional[list] = None
    difficulty: str
    created_at: datetime


@router.post("/quiz", response_model=List[QuizQuestionItem])
async def generate_quiz(
    req: QuizGenerateRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    service = StudyService(session)
    return await service.generate_quiz(
        user_id=current_user.id,
        topic=req.topic,
        num_questions=req.num_questions,
        difficulty=req.difficulty,
    )


@router.post("/flashcards", response_model=List[FlashcardItem])
async def generate_flashcards(
    req: FlashcardGenerateRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    service = StudyService(session)
    return await service.generate_flashcards(
        user_id=current_user.id,
        topic=req.topic,
        count=req.count,
        difficulty=req.difficulty,
    )


@router.post("/viva", response_model=List[VivaQuestionItem])
async def generate_viva(
    req: VivaGenerateRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    service = StudyService(session)
    return await service.generate_viva_questions(
        user_id=current_user.id,
        topic=req.topic,
        count=req.count,
        difficulty=req.difficulty,
    )


@router.post("/plan", response_model=Dict[str, Any])
async def generate_study_plan(
    req: StudyPlanRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    service = StudyService(session)
    return await service.generate_study_plan(
        user_id=current_user.id,
        subject=req.subject,
        duration_weeks=req.duration_weeks,
        hours_per_week=req.hours_per_week,
    )


@router.post("/summary", response_model=Dict[str, str])
async def generate_revision_summary(
    req: RevisionSummaryRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    service = StudyService(session)
    return await service.generate_revision_summary(
        user_id=current_user.id,
        topic=req.topic,
    )


@router.post("/derivation", response_model=Dict[str, str])
async def generate_derivation(
    req: DerivationRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    service = StudyService(session)
    return await service.generate_derivation(
        user_id=current_user.id,
        concept=req.concept,
    )


@router.post("/compare", response_model=Dict[str, str])
async def generate_topic_comparison(
    req: TopicComparisonRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    service = StudyService(session)
    return await service.generate_topic_comparison(
        user_id=current_user.id,
        topic_a=req.topic_a,
        topic_b=req.topic_b,
    )


@router.get("/cards", response_model=List[StudyCardResponse])
async def list_study_cards(
    card_type: Optional[str] = None,
    topic: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    repo = StudyRepository(session)
    cards = await repo.list_by_user(
        user_id=current_user.id,
        card_type=card_type,
        topic=topic,
        limit=limit,
        offset=offset,
    )
    return [
        StudyCardResponse(
            id=c.id,
            card_type=c.card_type,
            topic=c.topic,
            question=c.question,
            answer=c.answer,
            explanation=c.explanation,
            options=c.options,
            difficulty=c.difficulty,
            created_at=c.created_at,
        )
        for c in cards
    ]
