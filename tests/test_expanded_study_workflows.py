import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.study.service import StudyService
from app.llm.schemas import LLMResponse, ProviderName


@pytest.mark.asyncio
async def test_generate_viva_questions():
    mock_session = AsyncMock()
    mock_router = MagicMock()

    viva_json = """
    [
      {
        "viva_question": "Explain the Frank-Starling mechanism.",
        "model_answer": "Stroke volume increases proportionally to end-diastolic volume.",
        "key_examiner_points": ["Myocyte stretch", "Preload dependence"],
        "difficulty": "medium"
      }
    ]
    """
    mock_router.execute_with_fallback = AsyncMock(
        return_value=LLMResponse(
            content=viva_json,
            provider=ProviderName.GROQ,
            model="llama-3.3-70b-versatile",
            tokens_used=120,
            latency_ms=150.0,
        )
    )

    service = StudyService(session=mock_session, router=mock_router)
    with patch.object(service.repo, "create_card", new_callable=AsyncMock) as mock_create_card:
        viva_list = await service.generate_viva_questions(
            user_id="user-1",
            topic="Cardiovascular Physiology",
            count=1,
            difficulty="medium",
        )

        assert len(viva_list) == 1
        assert viva_list[0].viva_question == "Explain the Frank-Starling mechanism."
        assert len(viva_list[0].key_examiner_points) == 2
        mock_create_card.assert_called_once()


@pytest.mark.asyncio
async def test_generate_study_plan():
    mock_session = AsyncMock()
    mock_router = MagicMock()

    plan_json = """
    {
      "subject": "Organic Chemistry",
      "total_weeks": 2,
      "weekly_plan": [
        {
          "week_number": 1,
          "theme": "Alkanes and Alkenes",
          "learning_objectives": ["Nomenclature", "Electrophilic addition"],
          "recommended_hours": 10
        }
      ],
      "exam_revision_strategy": "Flashcard repetition"
    }
    """
    mock_router.execute_with_fallback = AsyncMock(
        return_value=LLMResponse(
            content=plan_json,
            provider=ProviderName.GROQ,
            model="llama-3.3-70b-versatile",
            tokens_used=200,
            latency_ms=210.0,
        )
    )

    service = StudyService(session=mock_session, router=mock_router)
    plan = await service.generate_study_plan(
        user_id="user-1",
        subject="Organic Chemistry",
        duration_weeks=2,
        hours_per_week=10,
    )

    assert plan["subject"] == "Organic Chemistry"
    assert plan["total_weeks"] == 2
    assert len(plan["weekly_plan"]) == 1
    assert plan["weekly_plan"][0]["theme"] == "Alkanes and Alkenes"


@pytest.mark.asyncio
async def test_generate_derivation():
    mock_session = AsyncMock()
    mock_router = MagicMock()

    mock_router.execute_with_fallback = AsyncMock(
        return_value=LLMResponse(
            content="### Step 1: State the kinetic equation...\n### Step 2: Integrate over interval...",
            provider=ProviderName.GROQ,
            model="llama-3.3-70b-versatile",
            tokens_used=180,
            latency_ms=190.0,
        )
    )

    service = StudyService(session=mock_session, router=mock_router)
    derivation = await service.generate_derivation(
        user_id="user-1",
        concept="Michaelis-Menten Equation",
    )

    assert derivation["concept"] == "Michaelis-Menten Equation"
    assert "Step 1: State the kinetic equation" in derivation["derivation"]
