import pytest
from unittest.mock import AsyncMock, MagicMock
from app.rag.hybrid import HybridRetriever
from app.rag.vector_store import RetrievedChunk


@pytest.mark.asyncio
async def test_parent_child_context_expansion():
    mock_session = AsyncMock()

    # Mock DB result for parent chunk lookup
    parent_mock = MagicMock()
    parent_mock.id = "parent-chunk-123"
    parent_mock.content = "Section 4.1: Cellular Bioenergetics and ATP Synthase Mechanisms in Mitochondria."

    mock_db_res = MagicMock()
    mock_db_res.scalars.return_value.all.return_value = [parent_mock]
    mock_session.execute.return_value = mock_db_res

    retriever = HybridRetriever(session=mock_session)

    child_chunk = RetrievedChunk(
        chunk_id="child-chunk-01",
        document_id="doc-99",
        filename="Biochemistry.pdf",
        page_number=142,
        content="ATP synthase synthesizes ATP from ADP and inorganic phosphate.",
        similarity_score=0.89,
        parent_chunk_id="parent-chunk-123",
        section_title="Mitochondrial respiration",
    )

    expanded_chunks = await retriever._expand_parent_context(
        candidates=[child_chunk],
        user_id="user-123",
    )

    assert len(expanded_chunks) == 1
    expanded = expanded_chunks[0]
    assert "Section 4.1: Cellular Bioenergetics" in expanded.content
    assert "ATP synthase synthesizes ATP" in expanded.content
    assert expanded.page_number == 142
    assert expanded.filename == "Biochemistry.pdf"
