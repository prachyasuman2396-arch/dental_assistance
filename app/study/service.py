import json
import re
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.repositories.study_repo import StudyRepository
from app.llm.router import LLMRouter
from app.llm.schemas import TaskType, ComplexityLevel, LLMMessage
from app.prompts.study import (
    QUIZ_GENERATION_PROMPT,
    FLASHCARD_GENERATION_PROMPT,
    STUDY_PLAN_PROMPT,
    REVISION_SUMMARY_PROMPT,
    DERIVATION_PROMPT,
    VIVA_PRACTICE_PROMPT,
    TOPIC_COMPARISON_PROMPT,
)
from app.core.logging import logger


class MCQOption(BaseModel):
    label: str
    text: str


class QuizQuestionItem(BaseModel):
    question: str
    options: List[str]
    correct_answer: str
    explanation: str
    difficulty: str = "medium"


class FlashcardItem(BaseModel):
    question: str
    answer: str
    topic: str
    difficulty: str = "medium"


class VivaQuestionItem(BaseModel):
    viva_question: str
    model_answer: str
    key_examiner_points: List[str] = Field(default_factory=list)
    difficulty: str = "medium"


class StudyService:
    def __init__(self, session: AsyncSession, router: Optional[LLMRouter] = None):
        self.session = session
        self.repo = StudyRepository(session)
        self.router = router or LLMRouter()

    async def generate_quiz(
        self,
        user_id: str,
        topic: str,
        num_questions: int = 3,
        difficulty: str = "medium",
    ) -> List[QuizQuestionItem]:
        prompt = (
            f"Generate {num_questions} high-yield examination MCQs on the topic: '{topic}'. "
            f"Difficulty level: {difficulty}."
        )
        messages = [
            LLMMessage(role="system", content=QUIZ_GENERATION_PROMPT),
            LLMMessage(role="user", content=prompt),
        ]

        res = await self.router.execute_with_fallback(
            task_type=TaskType.STUDY_GENERATION,
            messages=messages,
            complexity=ComplexityLevel.LOW,
            temperature=0.3,
        )

        clean_content = re.sub(r"^```json\s*", "", res.content.strip())
        clean_content = re.sub(r"\s*```$", "", clean_content)

        try:
            items = json.loads(clean_content)
        except Exception as e:
            logger.warning(f"Failed to parse JSON quiz output: {e}")
            items = []

        quiz_questions: List[QuizQuestionItem] = []
        for item in items:
            q = QuizQuestionItem(
                question=item.get("question", ""),
                options=item.get("options", []),
                correct_answer=item.get("correct_answer", ""),
                explanation=item.get("explanation", ""),
                difficulty=item.get("difficulty", difficulty),
            )
            quiz_questions.append(q)

            # Persist to database
            await self.repo.create_card(
                user_id=user_id,
                topic=topic,
                card_type="mcq",
                question=q.question,
                answer=q.correct_answer,
                explanation=q.explanation,
                options=q.options,
                difficulty=q.difficulty,
            )

        return quiz_questions

    async def generate_flashcards(
        self,
        user_id: str,
        topic: str,
        count: int = 5,
        difficulty: str = "medium",
    ) -> List[FlashcardItem]:
        prompt = (
            f"Generate {count} active-recall study flashcards on the topic: '{topic}'. "
            f"Difficulty: {difficulty}."
        )
        messages = [
            LLMMessage(role="system", content=FLASHCARD_GENERATION_PROMPT),
            LLMMessage(role="user", content=prompt),
        ]

        res = await self.router.execute_with_fallback(
            task_type=TaskType.STUDY_GENERATION,
            messages=messages,
            complexity=ComplexityLevel.LOW,
            temperature=0.4,
        )

        clean_content = re.sub(r"^```json\s*", "", res.content.strip())
        clean_content = re.sub(r"\s*```$", "", clean_content)

        try:
            items = json.loads(clean_content)
        except Exception as e:
            logger.warning(f"Failed to parse JSON flashcard output: {e}")
            items = []

        flashcards: List[FlashcardItem] = []
        for item in items:
            fc = FlashcardItem(
                question=item.get("question", ""),
                answer=item.get("answer", ""),
                topic=item.get("topic", topic),
                difficulty=item.get("difficulty", difficulty),
            )
            flashcards.append(fc)

            # Persist to database
            await self.repo.create_card(
                user_id=user_id,
                topic=fc.topic,
                card_type="flashcard",
                question=fc.question,
                answer=fc.answer,
                explanation=None,
                options=[],
                difficulty=fc.difficulty,
            )

        return flashcards

    async def generate_viva_questions(
        self,
        user_id: str,
        topic: str,
        count: int = 3,
        difficulty: str = "medium",
    ) -> List[VivaQuestionItem]:
        prompt = (
            f"Generate {count} realistic academic viva voce examination questions on '{topic}'. "
            f"Difficulty: {difficulty}."
        )
        messages = [
            LLMMessage(role="system", content=VIVA_PRACTICE_PROMPT),
            LLMMessage(role="user", content=prompt),
        ]

        res = await self.router.execute_with_fallback(
            task_type=TaskType.STUDY_GENERATION,
            messages=messages,
            complexity=ComplexityLevel.LOW,
            temperature=0.3,
        )

        clean = re.sub(r"^```json\s*", "", res.content.strip())
        clean = re.sub(r"\s*```$", "", clean)

        try:
            items = json.loads(clean)
        except Exception as e:
            logger.warning(f"Failed to parse viva JSON: {e}")
            items = []

        viva_items: List[VivaQuestionItem] = []
        for item in items:
            v = VivaQuestionItem(
                viva_question=item.get("viva_question", ""),
                model_answer=item.get("model_answer", ""),
                key_examiner_points=item.get("key_examiner_points", []),
                difficulty=item.get("difficulty", difficulty),
            )
            viva_items.append(v)

            # Persist to study cards
            await self.repo.create_card(
                user_id=user_id,
                topic=topic,
                card_type="viva",
                question=v.viva_question,
                answer=v.model_answer,
                explanation=f"Key Examiner Points: {', '.join(v.key_examiner_points)}",
                options=v.key_examiner_points,
                difficulty=v.difficulty,
            )

        return viva_items

    async def generate_study_plan(
        self,
        user_id: str,
        subject: str,
        duration_weeks: int = 4,
        hours_per_week: int = 10,
    ) -> Dict[str, Any]:
        prompt = (
            f"Subject: {subject}\n"
            f"Target Duration: {duration_weeks} weeks\n"
            f"Target Study Time: {hours_per_week} hours per week\n"
            "Generate the comprehensive study plan JSON."
        )
        messages = [
            LLMMessage(role="system", content=STUDY_PLAN_PROMPT),
            LLMMessage(role="user", content=prompt),
        ]

        res = await self.router.execute_with_fallback(
            task_type=TaskType.STUDY_GENERATION,
            messages=messages,
            complexity=ComplexityLevel.LOW,
            temperature=0.3,
        )

        clean = re.sub(r"^```json\s*", "", res.content.strip())
        clean = re.sub(r"\s*```$", "", clean)

        try:
            plan = json.loads(clean)
        except Exception as e:
            logger.warning(f"Failed to parse study plan JSON: {e}")
            plan = {
                "subject": subject,
                "total_weeks": duration_weeks,
                "weekly_plan": [],
                "raw_text": res.content,
            }

        return plan

    async def generate_revision_summary(
        self,
        user_id: str,
        topic: str,
    ) -> Dict[str, str]:
        messages = [
            LLMMessage(role="system", content=REVISION_SUMMARY_PROMPT),
            LLMMessage(role="user", content=f"Create a high-yield rapid revision summary for: {topic}"),
        ]

        res = await self.router.execute_with_fallback(
            task_type=TaskType.TUTOR,
            messages=messages,
            complexity=ComplexityLevel.LOW,
            temperature=0.4,
        )

        return {"topic": topic, "summary": res.content}

    async def generate_derivation(
        self,
        user_id: str,
        concept: str,
    ) -> Dict[str, str]:
        messages = [
            LLMMessage(role="system", content=DERIVATION_PROMPT),
            LLMMessage(role="user", content=f"Provide a step-by-step mathematical/logical derivation for: {concept}"),
        ]

        res = await self.router.execute_with_fallback(
            task_type=TaskType.TUTOR,
            messages=messages,
            complexity=ComplexityLevel.MEDIUM,
            temperature=0.3,
        )

        return {"concept": concept, "derivation": res.content}

    async def generate_topic_comparison(
        self,
        user_id: str,
        topic_a: str,
        topic_b: str,
    ) -> Dict[str, str]:
        messages = [
            LLMMessage(role="system", content=TOPIC_COMPARISON_PROMPT),
            LLMMessage(role="user", content=f"Compare and contrast '{topic_a}' versus '{topic_b}' in depth."),
        ]

        res = await self.router.execute_with_fallback(
            task_type=TaskType.TUTOR,
            messages=messages,
            complexity=ComplexityLevel.MEDIUM,
            temperature=0.4,
        )

        return {"topic_a": topic_a, "topic_b": topic_b, "comparison": res.content}
