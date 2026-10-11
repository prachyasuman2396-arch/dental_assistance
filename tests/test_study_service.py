import pytest
from unittest.mock import AsyncMock, MagicMock
from app.study.service import StudyService
from app.llm.schemas import LLMResponse, ProviderName


@pytest.mark.asyncio
async def test_study_service_generates_quiz_mcqs(mock_router):
    mock_session = AsyncMock()
    mock_router.execute_with_fallback = AsyncMock(
        return_value=LLMResponse(
            content='''[
                {
                    "question": "Which cell is responsible for secondary dentin deposition?",
                    "options": ["Ameloblast", "Odontoblast", "Cementoblast", "Fibroblast"],
                    "correct_answer": "Odontoblast",
                    "explanation": "Odontoblasts remain vital in the dental pulp and lay down secondary and tertiary dentin.",
                    "difficulty": "easy"
                }
            ]''',
            provider=ProviderName.GROQ,
            model="llama-3.3-70b-versatile",
        )
    )

    service = StudyService(session=mock_session, router=mock_router)
    # Mock repo create_card
    service.repo.create_card = AsyncMock()

    questions = await service.generate_quiz(
        user_id="student-1",
        topic="Dentinogenesis",
        num_questions=1,
    )

    assert len(questions) == 1
    assert questions[0].correct_answer == "Odontoblast"
    assert "Ameloblast" in questions[0].options
    assert service.repo.create_card.called


@pytest.mark.asyncio
async def test_study_service_generates_flashcards(mock_router):
    mock_session = AsyncMock()
    mock_router.execute_with_fallback = AsyncMock(
        return_value=LLMResponse(
            content='''[
                {
                    "question": "What is the primary action of 2% chlorhexidine in endodontics?",
                    "answer": "Broad-spectrum antimicrobial activity with substantivity, but lacks tissue-dissolving capacity.",
                    "topic": "Endodontic Irrigants",
                    "difficulty": "medium"
                }
            ]''',
            provider=ProviderName.GROQ,
            model="llama-3.3-70b-versatile",
        )
    )

    service = StudyService(session=mock_session, router=mock_router)
    service.repo.create_card = AsyncMock()

    cards = await service.generate_flashcards(
        user_id="student-1",
        topic="Endodontic Irrigants",
        count=1,
    )

    assert len(cards) == 1
    assert "chlorhexidine" in cards[0].question.lower()
    assert "substantivity" in cards[0].answer.lower()
    assert service.repo.create_card.called
