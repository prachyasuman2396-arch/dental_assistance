import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.api.dependencies import get_current_user, get_db
from app.db.models.user import User
from app.db.models.profile import UserProfile
from app.db.models.memory import LongTermMemory
from app.db.repositories.profile_repo import ProfileRepository
from app.db.repositories.memory_repo import MemoryRepository


@pytest.fixture
def student_user_1():
    return User(
        id="usr-stud-001",
        email="alex@university.edu",
        hashed_password="pw",
        full_name="Alex Rivera",
        academic_level="Undergraduate",
        is_active=True,
    )


@pytest.fixture
def student_user_2():
    return User(
        id="usr-stud-002",
        email="sam@university.edu",
        hashed_password="pw",
        full_name="Sam Patel",
        academic_level="Graduate",
        is_active=True,
    )


@pytest.mark.asyncio
async def test_profile_repository_create_and_update():
    session = AsyncMock()

    # Simulate no existing profile first
    mock_res_empty = MagicMock()
    mock_res_empty.scalar_one_or_none.return_value = None
    session.execute = AsyncMock(return_value=mock_res_empty)

    repo = ProfileRepository(session)
    profile = await repo.create_or_update(
        user_id="usr-stud-001",
        preferred_name="Alex",
        academic_institution="State University",
        academic_discipline="Computer Science",
        current_level="Senior",
        explanation_style="concise with code examples",
        learning_goals=["Master distributed algorithms", "Pass finals"],
    )

    assert profile.user_id == "usr-stud-001"
    assert profile.preferred_name == "Alex"
    assert profile.academic_discipline == "Computer Science"
    assert len(profile.learning_goals) == 2
    session.add.assert_called_once()
    session.commit.assert_called_once()

    # Simulate existing profile for update
    existing_prof = UserProfile(
        id="prof-1",
        user_id="usr-stud-001",
        preferred_name="Alex",
        academic_discipline="Computer Science",
        current_level="Senior",
        explanation_style="concise",
        learning_goals=["Master algorithms"],
    )
    mock_res_existing = MagicMock()
    mock_res_existing.scalar_one_or_none.return_value = existing_prof
    session.execute = AsyncMock(return_value=mock_res_existing)

    updated_prof = await repo.create_or_update(
        user_id="usr-stud-001",
        current_level="Master's Student",
    )
    assert updated_prof.current_level == "Master's Student"
    assert updated_prof.preferred_name == "Alex"  # preserved


@pytest.mark.asyncio
async def test_memory_repository_deduplication():
    session = AsyncMock()
    repo = MemoryRepository(session)

    # 1. Existing memory found -> deduplicate
    existing_mem = LongTermMemory(
        id="mem-100",
        user_id="usr-stud-001",
        memory_type="study_goal",
        content="Prepare for operating systems exam",
        topic="OS",
        importance=2,
    )
    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = existing_mem
    session.execute = AsyncMock(return_value=mock_res)

    result = await repo.add_memory(
        user_id="usr-stud-001",
        memory_type="study_goal",
        content="Prepare for operating systems exam",
        topic="OS",
    )

    assert result.id == "mem-100"
    session.add.assert_not_called()  # Deduplicated!


@pytest.mark.asyncio
async def test_memory_repository_user_isolation(student_user_1, student_user_2):
    session = AsyncMock()
    repo = MemoryRepository(session)

    # Attempt to delete student_user_1's memory by student_user_2
    mock_res = MagicMock()
    mock_res.rowcount = 0  # 0 rows affected due to user_id filter
    session.execute = AsyncMock(return_value=mock_res)

    deleted = await repo.delete_memory(memory_id="mem-100", user_id=student_user_2.id)
    assert deleted is False
    session.delete.assert_not_called()


@pytest.mark.asyncio
async def test_profile_api_endpoints(student_user_1):
    app.dependency_overrides[get_current_user] = lambda: student_user_1
    mock_db = AsyncMock()
    app.dependency_overrides[get_db] = lambda: mock_db

    fake_profile = UserProfile(
        id="prof-1",
        user_id=student_user_1.id,
        preferred_name="Alex",
        academic_institution="Global Tech Institute",
        academic_discipline="Data Science",
        current_level="3rd Year",
        explanation_style="Socratic",
        learning_goals=["Deep Learning", "Transformers"],
    )

    with patch.object(ProfileRepository, "get_by_user_id", new_callable=AsyncMock) as mock_get, \
         patch.object(ProfileRepository, "create_or_update", new_callable=AsyncMock) as mock_update:

        mock_get.return_value = fake_profile
        mock_update.return_value = fake_profile

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # GET /api/v1/profile
            get_res = await client.get("/api/v1/profile")
            assert get_res.status_code == 200
            assert get_res.json()["preferred_name"] == "Alex"
            assert get_res.json()["academic_discipline"] == "Data Science"

            # PUT /api/v1/profile
            put_res = await client.put(
                "/api/v1/profile",
                json={
                    "preferred_name": "Alex R.",
                    "explanation_style": "Step-by-step with analogies",
                },
            )
            assert put_res.status_code == 200

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_memories_api_endpoints(student_user_1):
    app.dependency_overrides[get_current_user] = lambda: student_user_1
    mock_db = AsyncMock()
    app.dependency_overrides[get_db] = lambda: mock_db

    sample_mem = LongTermMemory(
        id="mem-999",
        user_id=student_user_1.id,
        memory_type="saved_topic",
        topic="Bayesian Inference",
        content="Remember prior and posterior distributions formulas",
        importance=2,
    )

    with patch.object(MemoryRepository, "get_memories", new_callable=AsyncMock) as mock_list, \
         patch.object(MemoryRepository, "add_memory", new_callable=AsyncMock) as mock_add, \
         patch.object(MemoryRepository, "delete_memory", new_callable=AsyncMock) as mock_del:

        mock_list.return_value = [sample_mem]
        mock_add.return_value = sample_mem
        mock_del.return_value = True

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # GET /api/v1/memories
            list_res = await client.get("/api/v1/memories")
            assert list_res.status_code == 200
            data = list_res.json()
            assert len(data) == 1
            assert data[0]["topic"] == "Bayesian Inference"

            # POST /api/v1/memories
            post_res = await client.post(
                "/api/v1/memories",
                json={
                    "memory_type": "saved_topic",
                    "topic": "Bayesian Inference",
                    "content": "Remember prior and posterior distributions formulas",
                    "importance": 2,
                },
            )
            assert post_res.status_code == 201
            assert post_res.json()["id"] == "mem-999"

            # DELETE /api/v1/memories/mem-999
            del_res = await client.delete("/api/v1/memories/mem-999")
            assert del_res.status_code == 200
            assert del_res.json()["deleted"] is True

    app.dependency_overrides.clear()
