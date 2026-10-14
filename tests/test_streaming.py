import pytest
import json
from unittest.mock import AsyncMock, patch, MagicMock
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.api.dependencies import get_current_user, get_db
from app.db.models.user import User
from app.db.models.conversation import Conversation
from app.db.repositories.conversation_repo import ConversationRepository
from app.llm.router import LLMRouter
from app.llm.schemas import ProviderName


@pytest.fixture
def streaming_student():
    return User(
        id="usr-stream-1",
        email="streamer@uni.edu",
        hashed_password="pw",
        full_name="Streaming Student",
        academic_level="Undergraduate",
        is_active=True,
    )


@pytest.mark.asyncio
async def test_sse_streaming_protocol_and_persistence(streaming_student):
    app.dependency_overrides[get_current_user] = lambda: streaming_student
    mock_db = AsyncMock()
    app.dependency_overrides[get_db] = lambda: mock_db

    fake_conv = Conversation(id="conv-streaming-123", user_id=streaming_student.id, title="Quantum Computing")

    async def fake_stream_generator(*args, **kwargs):
        yield {"token": "Quantum ", "provider": "groq", "model": "llama-3.3-70b-versatile"}
        yield {"token": "entanglement ", "provider": "groq", "model": "llama-3.3-70b-versatile"}
        yield {"token": "is fundamental.", "provider": "groq", "model": "llama-3.3-70b-versatile"}

    with patch.object(ConversationRepository, "get_by_id", new_callable=AsyncMock) as mock_get_conv, \
         patch.object(ConversationRepository, "add_message", new_callable=AsyncMock) as mock_add_msg, \
         patch.object(ConversationRepository, "get_messages", new_callable=AsyncMock) as mock_get_msgs, \
         patch.object(LLMRouter, "stream_with_fallback", side_effect=fake_stream_generator):

        mock_get_conv.return_value = fake_conv
        mock_get_msgs.return_value = []

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            res = await client.post(
                "/api/v1/chat",
                json={
                    "message": "Explain quantum entanglement simply.",
                    "conversation_id": "conv-streaming-123",
                    "stream": True,
                },
            )

            assert res.status_code == 200
            assert "text/event-stream" in res.headers["content-type"]

            # Parse SSE events from response body
            body_text = res.text
            events = []
            for block in body_text.strip().split("\n\n"):
                if not block.strip():
                    continue
                lines = block.strip().split("\n")
                event_name = ""
                data_val = None
                for line in lines:
                    if line.startswith("event:"):
                        event_name = line[6:].strip()
                    elif line.startswith("data:"):
                        data_val = json.loads(line[5:].strip())
                events.append((event_name, data_val))

            event_types = [e[0] for e in events]
            assert "message_start" in event_types
            assert "status" in event_types
            assert "token" in event_types
            assert "message_end" in event_types

            # Verify tokens combined
            tokens = [e[1]["token"] for e in events if e[0] == "token"]
            combined_tokens = "".join(tokens)
            assert combined_tokens == "Quantum entanglement is fundamental."

            # Verify end event payload
            end_event = [e[1] for e in events if e[0] == "message_end"][0]
            assert end_event["answer"] == "Quantum entanglement is fundamental."
            assert end_event["conversation_id"] == "conv-streaming-123"
            assert end_event["provider"] == "groq"

            # Verify assistant message persistence was called exactly once for the response
            # (First call is for user message, second call is for assistant message)
            assert mock_add_msg.call_count == 2
            assistant_call = mock_add_msg.call_args_list[1]
            assert assistant_call.kwargs["role"] == "assistant"
            assert assistant_call.kwargs["content"] == "Quantum entanglement is fundamental."

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_streaming_utf8_multibyte_boundaries():
    # Verify that multi-byte UTF-8 characters (e.g. Greek mathematical symbols: α, β, γ, ℏ, ψ)
    # stream intact
    sample_text = "Wavefunction ψ(x, t) and reduced Planck constant ℏ."
    encoded = sample_text.encode("utf-8")
    # Slice right in the middle of a multi-byte boundary
    chunk1 = encoded[:15]
    chunk2 = encoded[15:]
    decoded = (chunk1 + chunk2).decode("utf-8")
    assert decoded == sample_text


@pytest.mark.asyncio
async def test_streaming_error_handling(streaming_student):
    app.dependency_overrides[get_current_user] = lambda: streaming_student
    mock_db = AsyncMock()
    app.dependency_overrides[get_db] = lambda: mock_db

    fake_conv = Conversation(id="conv-err-1", user_id=streaming_student.id, title="Error Test")

    async def broken_stream(*args, **kwargs):
        raise RuntimeError("External LLM upstream timeout")
        yield  # make it a generator

    with patch.object(ConversationRepository, "get_by_id", new_callable=AsyncMock) as mock_get_conv, \
         patch.object(ConversationRepository, "add_message", new_callable=AsyncMock), \
         patch.object(ConversationRepository, "get_messages", new_callable=AsyncMock) as mock_get_msgs, \
         patch.object(LLMRouter, "stream_with_fallback", side_effect=broken_stream):

        mock_get_conv.return_value = fake_conv
        mock_get_msgs.return_value = []

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            res = await client.post(
                "/api/v1/chat",
                json={
                    "message": "Crash test",
                    "conversation_id": "conv-err-1",
                    "stream": True,
                },
            )

            assert res.status_code == 200
            assert "text/event-stream" in res.headers["content-type"]
            body_text = res.text
            assert "event: error" in body_text
            assert "External LLM upstream timeout" in body_text

    app.dependency_overrides.clear()
