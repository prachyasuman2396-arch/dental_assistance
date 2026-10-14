import pytest
import os
import tempfile
import pymupdf
from unittest.mock import AsyncMock, MagicMock
from app.documents.parser import PDFParser
from app.rag.splitter import StructureAwareSplitter, HierarchicalChunk
from app.rag.embeddings import EmbeddingCache, FastEmbedEmbeddingProvider
from app.rag.query_analysis import QueryAnalyzer
from app.rag.reranker import CrossEncoderReranker
from app.rag.compression import ContextCompressor
from app.rag.sufficiency import EvidenceSufficiencyChecker
from app.rag.vector_store import RetrievedChunk, PgVectorRetriever
from app.rag.hybrid import HybridRetriever, RetrievalCache
from app.db.models.chunk import DocumentChunk
from app.db.models.document import Document


# 1. Validation and Extraction Tests
def test_pdf_magic_byte_validation_and_deduplication():
    # Valid PDF
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as valid_pdf:
        valid_path = valid_pdf.name
        doc = pymupdf.open()
        p = doc.new_page()
        p.insert_text((50, 50), "Standard Model of Particle Physics: Quarks and Leptons.")
        doc.save(valid_path)
        doc.close()

    # Fake disguised script
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as fake_pdf:
        fake_path = fake_pdf.name
        fake_pdf.write(b"#!/bin/bash\necho 'malicious'")

    try:
        assert PDFParser.validate_pdf_magic(valid_path) is True
        assert PDFParser.validate_pdf_magic(fake_path) is False

        # File hash computation
        h1 = PDFParser.compute_file_sha256(valid_path)
        h2 = PDFParser.compute_file_sha256(valid_path)
        assert h1 == h2
        assert len(h1) == 64
    finally:
        if os.path.exists(valid_path):
            os.remove(valid_path)
        if os.path.exists(fake_path):
            os.remove(fake_path)


# 2. Structure-Aware & Parent-Child Chunking
def test_structure_aware_parent_child_chunking():
    splitter = StructureAwareSplitter(
        child_chunk_size=150,
        child_overlap=30,
        parent_chunk_size=400,
        enable_parent_child=True,
    )
    long_academic_text = (
        "Cellular respiration is a metabolic pathway that breaks down glucose and produces ATP. "
        "The stages include glycolysis, pyruvate oxidation, the citric acid cycle, and oxidative phosphorylation. "
        "Glycolysis takes place in the cytosol of the cell, converting one six-carbon molecule of glucose into two "
        "three-carbon molecules of pyruvate while yielding two net ATP molecules and two NADH molecules."
    )

    chunks = splitter.split_page(
        text=long_academic_text,
        page_number=5,
        section_title="Metabolism",
    )

    assert len(chunks) > 1
    # Check parent chunks exist
    parent_chunks = [c for c in chunks if c.is_parent]
    child_chunks = [c for c in chunks if not c.is_parent]

    assert len(parent_chunks) >= 1
    assert len(child_chunks) >= 1
    # Verify child chunks link to valid parent ID
    for child in child_chunks:
        assert child.parent_chunk_id is not None
        assert any(p.chunk_id == child.parent_chunk_id for p in parent_chunks)
        assert child.section_title == "Metabolism"
        assert child.page_start == 5


# 3. Query Analysis & Contextual Rewriting
@pytest.mark.asyncio
async def test_query_analyzer_heuristic_and_standalone():
    analyzer = QueryAnalyzer()

    # Query with pronoun referring to history
    history = [
        {"role": "user", "content": "What is the function of mitochondria?"},
        {"role": "assistant", "content": "Mitochondria generate most of the chemical energy needed by the cell."},
    ]
    follow_up = "What are its key enzymes?"

    result = await analyzer.analyze_and_rewrite(
        current_query=follow_up,
        conversation_history=history,
    )

    assert result.original_query == follow_up
    assert "mitochondria" in result.standalone_query.lower() or "enzymes" in result.standalone_query.lower()
    assert result.retrieval_needed is True


# 4. Cross-Encoder Reranker
@pytest.mark.asyncio
async def test_cross_encoder_reranking_accuracy():
    reranker = CrossEncoderReranker()
    query = "How does DNA polymerase proofread newly synthesized strands?"

    c1_irrelevant = RetrievedChunk(
        chunk_id="c1",
        document_id="doc-1",
        filename="genetics.pdf",
        page_number=10,
        content="Ribosomes are macromolecular machines responsible for synthesizing polypeptides from mRNA transcripts.",
        similarity_score=0.70,  # initial vector similarity was mistakenly high
    )

    c2_relevant = RetrievedChunk(
        chunk_id="c2",
        document_id="doc-1",
        filename="genetics.pdf",
        page_number=25,
        content="DNA polymerase possesses 3' to 5' exonuclease activity that proofreads newly added nucleotides, removing mismatches.",
        similarity_score=0.65,
    )

    reranked = await reranker.rerank(query, [c1_irrelevant, c2_relevant], top_k=2)

    # c2 contains direct key terms: "DNA polymerase", "proofreads", "exonuclease"
    # so cross-encoder must promote c2 to rank 1!
    assert reranked[0].chunk_id == "c2"
    assert reranked[0].similarity_score > reranked[1].similarity_score


# 5. Contextual Compression
def test_contextual_compression_sentence_filtering():
    compressor = ContextCompressor(max_characters_budget=500)
    query = "action potential depolarization"

    chunk = RetrievedChunk(
        chunk_id="c1",
        document_id="doc-neuro",
        filename="neuroscience.pdf",
        page_number=45,
        content=(
            "Neurons have a resting membrane potential of approximately -70 millivolts. "
            "Action potential depolarization is triggered by the rapid influx of sodium ions through voltage-gated channels. "
            "The brain consumes approximately twenty percent of the body's total oxygen supply. "
            "Glial cells provide essential metabolic and structural support throughout the central nervous system."
        ),
        similarity_score=0.85,
    )

    compressed = compressor.compress_chunk(chunk, query)
    assert "depolarization" in compressed
    assert "sodium ions" in compressed
    # Irrelevant sentence about general brain oxygen consumption should be omitted
    assert "twenty percent" not in compressed


# 6. Evidence Sufficiency Verification
def test_evidence_sufficiency_checker():
    checker = EvidenceSufficiencyChecker(min_term_coverage=0.50, min_top_similarity=0.30)

    # Test sufficient evidence
    chunks_sufficient = [
        RetrievedChunk(
            chunk_id="chk-1",
            document_id="doc-1",
            filename="physics.pdf",
            page_number=12,
            content="Photoelectric effect occurs when photons transfer energy to electrons, ejecting them from the metal surface.",
            similarity_score=0.88,
        )
    ]
    eval_sufficient = checker.evaluate("photoelectric effect electron ejection", chunks_sufficient)
    assert eval_sufficient.is_sufficient is True
    assert eval_sufficient.confidence_score > 0.60
    assert eval_sufficient.recommendation == "proceed"

    # Test insufficient evidence (missing core technical aspects)
    eval_insufficient = checker.evaluate(
        "quantum chromodynamics gluon color confinement",
        chunks_sufficient,
    )
    assert eval_insufficient.is_sufficient is False
    assert len(eval_insufficient.missing_aspects) > 0


# 7. Embedding & Retrieval Caching
def test_embedding_and_retrieval_cache():
    e_cache = EmbeddingCache(capacity=2)
    k1 = e_cache.make_key("model-1", "Newton's second law")
    k2 = e_cache.make_key("model-1", "Faraday's induction")
    k3 = e_cache.make_key("model-1", "Kepler's orbits")

    e_cache.put(k1, [0.1, 0.2])
    e_cache.put(k2, [0.3, 0.4])
    assert e_cache.get(k1) == [0.1, 0.2]

    # Adding third exceeds capacity -> evicts least recently used
    e_cache.put(k3, [0.5, 0.6])
    assert e_cache.get(k3) == [0.5, 0.6]


# 8. Multi-Stage Pipeline Retrieve with Telemetry
@pytest.mark.asyncio
async def test_multi_stage_pipeline_retrieve():
    session = AsyncMock()
    mock_vector = AsyncMock(spec=PgVectorRetriever)

    v_chunk = RetrievedChunk(
        chunk_id="chk-10",
        document_id="doc-10",
        filename="microbiology.pdf",
        page_number=3,
        content="Gram-negative bacteria have a thin peptidoglycan layer enclosed by an outer membrane with lipopolysaccharides.",
        similarity_score=0.85,
    )
    mock_vector.similarity_search.return_value = [v_chunk]

    mock_db_res = MagicMock()
    mock_db_res.all.return_value = []
    session.execute.return_value = mock_db_res

    retriever = HybridRetriever(session=session, vector_retriever=mock_vector)

    results, metrics, evaluation = await retriever.pipeline_retrieve(
        query="Gram-negative bacteria outer membrane peptidoglycan",
        user_id="user-123",
        top_k=3,
    )

    assert len(results) == 1
    assert results[0].chunk_id == "chk-10"
    assert metrics.total_retrieval_ms > 0.0
    assert metrics.final_evidence_count == 1
    assert evaluation.is_sufficient is True
