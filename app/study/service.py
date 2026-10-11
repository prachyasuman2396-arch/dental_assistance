import json
import re
from typing import List, Optional
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.repositories.study_repo import StudyRepository
from app.llm.router import LLMRouter
from app.llm.schemas import TaskType, ComplexityLevel, LLMMessage
from app.prompts.study import QUIZ_GENERATION_PROMPT, FLASHCARD_GENERATION_PROMPT
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
            f"Generate {num_questions} high-yield dental examination MCQs on the topic: '{topic}'. "
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
            f"Generate {count} active-recall dental study flashcards on the topic: '{topic}'. "
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
