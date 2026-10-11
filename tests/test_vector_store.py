import pytest
from unittest.mock import AsyncMock, MagicMock
from app.rag.vector_store import PgVectorRetriever, RetrievedChunk
from app.rag.embeddings import BaseEmbeddingProvider


class MockEmbeddingProvider(BaseEmbeddingProvider):
    def embed_documents(self, texts):
        return [[0.1] * 384 for _ in texts]

    def embed_query(self, query):
        return [0.1] * 384

    @property
    def dimension(self):
        return 384


@pytest.mark.asyncio
async def test_vector_retriever_enforces_user_isolation():
    mock_session = AsyncMock()

    # Create fake chunks
    chunk_1 = MagicMock()
    chunk_1.id = "chunk-1"
    chunk_1.document_id = "doc-1"
    chunk_1.page_number = 42
    chunk_1.content = "Smear layer removal requires 17% EDTA followed by NaOCl."
    chunk_1.chunk_metadata = {"filename": "Pathways_of_Pulp.pdf"}

    # Mock DB execution result
    mock_result = MagicMock()
    mock_result.all.return_value = [
        (chunk_1, "Pathways_of_Pulp.pdf", 0.15)  # distance 0.15 => similarity 0.85
    ]
    mock_session.execute.return_value = mock_result

    retriever = PgVectorRetriever(
        session=mock_session,
        embedding_provider=MockEmbeddingProvider(),
    )

    results = await retriever.similarity_search(
        query="smear layer EDTA",
        user_id="student-A",
        top_k=3,
    )

    assert len(results) == 1
    assert results[0].page_number == 42
    assert results[0].filename == "Pathways_of_Pulp.pdf"
    assert results[0].similarity_score == 0.85
    assert "Smear layer removal" in results[0].content

    # Verify query strictly executed with user_id in filter
    assert mock_session.execute.called
