import pytest
import io
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, patch, MagicMock
from app.main import app
from app.api.dependencies import get_current_user, get_db
from app.db.models.user import User


@pytest.fixture
def test_user():
    return User(
        id="user-123",
        email="student@dental.edu",
        hashed_password="hashed_pw",
        full_name="Dental Student Alice",
        academic_level="BDS 3rd Year",
        is_active=True,
    )


@pytest.mark.asyncio
async def test_root_and_health_endpoints():
    mock_db = AsyncMock()
    # Mock scalar to return 1 synchronously
    mock_scalar_res = MagicMock()
    mock_scalar_res.scalar.return_value = 1
    mock_scalar_res.scalar_one_or_none.return_value = "vector"
    mock_db.execute = AsyncMock(return_value=mock_scalar_res)
    app.dependency_overrides[get_db] = lambda: mock_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Test Root
        root_res = await client.get("/")
        assert root_res.status_code == 200
        assert "Dental AI Study & Research Assistant" in root_res.json()["message"]

        # Test Health
        health_res = await client.get("/health")
        assert health_res.status_code == 200
        assert health_res.json()["database"] == "connected"
        assert health_res.json()["pgvector_extension"] == "installed"
        assert "embedding" in health_res.json()

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_auth_me_protected_endpoint(test_user):
    app.dependency_overrides[get_current_user] = lambda: test_user
    mock_db = AsyncMock()
    app.dependency_overrides[get_db] = lambda: mock_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/v1/auth/me")
        assert res.status_code == 200
        data = res.json()
        assert data["email"] == "student@dental.edu"
        assert data["academic_level"] == "BDS 3rd Year"

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_chat_endpoint_invocation(test_user):
    app.dependency_overrides[get_current_user] = lambda: test_user
    mock_db = AsyncMock()
    app.dependency_overrides[get_db] = lambda: mock_db

    # Mock ConversationRepository
    with patch("app.api.v1.chat.ConversationRepository") as mock_repo_cls, \
         patch("app.api.v1.chat.create_dental_graph") as mock_graph_builder:
        
        mock_repo = MagicMock()
        mock_conv = MagicMock()
        mock_conv.id = "conv-123"
        mock_repo.get_by_id = AsyncMock(return_value=mock_conv)
        mock_repo.create = AsyncMock(return_value=mock_conv)
        mock_repo.add_message = AsyncMock()
        mock_repo.get_messages = AsyncMock(return_value=[])
        mock_repo_cls.return_value = mock_repo

        mock_compiled_graph = MagicMock()
        mock_compiled_graph.ainvoke = AsyncMock(
            return_value={
                "answer": "Smear layer consists of microcrystalline debris created during canal instrumentation.",
                "citations": {"documents": [], "research_papers": []},
                "selected_provider": "groq",
                "selected_model": "llama-3.3-70b-versatile",
                "retrieved_chunks": [],
                "research_sources": [],
            }
        )
        mock_graph_builder.return_value = mock_compiled_graph

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            payload = {
                "message": "What is the endodontic smear layer composed of?",
            }
            res = await client.post("/api/v1/chat", json=payload)
            assert res.status_code == 200
            data = res.json()
            assert "Smear layer consists" in data["message"]
            assert data["provider"] == "groq"
            assert "conversation_id" in data

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_document_upload_rejects_non_pdf(test_user):
    app.dependency_overrides[get_current_user] = lambda: test_user
    mock_db = AsyncMock()
    app.dependency_overrides[get_db] = lambda: mock_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        files = {"file": ("notes.txt", io.BytesIO(b"Dental notes in text"), "text/plain")}
        res = await client.post("/api/v1/documents/upload", files=files)
        assert res.status_code == 400
        assert "Only PDF files are supported" in res.json()["detail"]

    app.dependency_overrides.clear()
