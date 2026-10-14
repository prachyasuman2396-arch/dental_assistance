import pytest
from unittest.mock import AsyncMock, MagicMock
from app.rag.hybrid import HybridRetriever, _tokenize
from app.rag.vector_store import RetrievedChunk, PgVectorRetriever
from app.db.models.chunk import DocumentChunk
from app.db.models.document import Document


def test_tokenize():
    tokens = _tokenize("Photosynthesis occurs in plant chloroplasts! (Light-dependent: Stage 1)")
    assert "photosynthesis" in tokens
    assert "chloroplasts" in tokens
    assert "stage" in tokens


@pytest.mark.asyncio
async def test_hybrid_retrieval_reciprocal_rank_fusion():
    session = AsyncMock()
    mock_vector = AsyncMock(spec=PgVectorRetriever)

    # 1. Mock dense vector results
    v_chunk_1 = RetrievedChunk(
        chunk_id="chk-v1",
        document_id="doc-1",
        filename="biology_textbook.pdf",
        page_number=12,
        content="Cellular respiration produces ATP via oxidative phosphorylation.",
        similarity_score=0.92,
    )
    v_chunk_2 = RetrievedChunk(
        chunk_id="chk-v2",
        document_id="doc-1",
        filename="biology_textbook.pdf",
        page_number=14,
        content="Glycolysis converts glucose into pyruvate in the cytoplasm.",
        similarity_score=0.75,
    )
    mock_vector.similarity_search.return_value = [v_chunk_1, v_chunk_2]

    # 2. Mock BM25 database chunks
    c1 = DocumentChunk(
        id="chk-bm1",
        document_id="doc-1",
        user_id="user-xyz",
        chunk_index=0,
        content="Oxidative phosphorylation occurs within the inner mitochondrial membrane.",
        page_number=15,
        content_hash="hash1",
    )
    c2 = DocumentChunk(
        id="chk-v1",  # Same chunk in BM25 to test rank fusion overlap
        document_id="doc-1",
        user_id="user-xyz",
        chunk_index=1,
        content="Cellular respiration produces ATP via oxidative phosphorylation.",
        page_number=12,
        content_hash="hash2",
    )
    doc_meta = Document(
        id="doc-1",
        user_id="user-xyz",
        filename="biology_textbook.pdf",
    )

    mock_db_res = MagicMock()
    # (DocumentChunk, Document)
    mock_db_res.all.return_value = [(c1, doc_meta), (c2, doc_meta)]
    session.execute.return_value = mock_db_res

    retriever = HybridRetriever(session=session, vector_retriever=mock_vector)

    results = await retriever.retrieve(
        query="oxidative phosphorylation ATP",
        user_id="user-xyz",
        top_k=3,
        vector_weight=0.6,
        bm25_weight=0.4,
    )

    assert len(results) > 0
    # chk-v1 was present in both dense vector and BM25, so its fused score should be highest!
    assert results[0].chunk_id == "chk-v1"
    assert results[0].similarity_score > 0.0
    assert results[0].filename == "biology_textbook.pdf"


@pytest.mark.asyncio
async def test_hybrid_retriever_empty_corpus():
    session = AsyncMock()
    mock_vector = AsyncMock(spec=PgVectorRetriever)
    mock_vector.similarity_search.return_value = []

    mock_db_res = MagicMock()
    mock_db_res.all.return_value = []
    session.execute.return_value = mock_db_res

    retriever = HybridRetriever(session=session, vector_retriever=mock_vector)
    results = await retriever.retrieve(
        query="nonexistent term",
        user_id="user-xyz",
        top_k=5,
    )

    assert results == []
