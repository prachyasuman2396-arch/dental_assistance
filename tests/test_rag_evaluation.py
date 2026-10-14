import pytest
from app.rag.vector_store import RetrievedChunk
from app.rag.evaluation import RAGEvaluator, BENCHMARK_STUDENT_DATASET, EvaluationSample


def test_rag_evaluator_metrics_computation():
    # Synthetic retrieved chunks for evaluation samples
    retrieved_results = {
        "eval-01": [
            RetrievedChunk(
                chunk_id="chk-atp-synthase-01",  # Relevant at rank 1
                document_id="doc-bio",
                filename="bio.pdf",
                page_number=10,
                content="ATP synthase rotates to produce ATP.",
                similarity_score=0.95,
            ),
            RetrievedChunk(
                chunk_id="chk-other",
                document_id="doc-bio",
                filename="bio.pdf",
                page_number=11,
                content="Other content",
                similarity_score=0.70,
            ),
        ],
        "eval-02": [
            RetrievedChunk(
                chunk_id="chk-distractor",  # Irrelevant at rank 1
                document_id="doc-gen",
                filename="gen.pdf",
                page_number=2,
                content="Polymerase chain reaction",
                similarity_score=0.80,
            ),
            RetrievedChunk(
                chunk_id="chk-crispr-01",  # Relevant at rank 2
                document_id="doc-gen",
                filename="gen.pdf",
                page_number=5,
                content="CRISPR Cas9 endonuclease cleavage",
                similarity_score=0.75,
            ),
        ],
        "eval-03": [
            RetrievedChunk(
                chunk_id="chk-photo-light-01",
                document_id="doc-botany",
                filename="botany.pdf",
                page_number=15,
                content="Thylakoid light reactions",
                similarity_score=0.90,
            ),
            RetrievedChunk(
                chunk_id="chk-photo-calvin-02",
                document_id="doc-botany",
                filename="botany.pdf",
                page_number=18,
                content="Stroma Calvin cycle rubisco",
                similarity_score=0.88,
            ),
        ],
        "eval-04": [
            RetrievedChunk(
                chunk_id="chk-mrna-immune-01",
                document_id="doc-immuno",
                filename="immuno.pdf",
                page_number=20,
                content="mRNA lipid nanoparticles generate spike proteins",
                similarity_score=0.92,
            )
        ],
        "eval-05": [],  # Negative sample
    }

    metrics = RAGEvaluator.evaluate_retrieval(retrieved_results=retrieved_results, k=2)

    assert metrics.total_queries == 4  # eval-05 has expected_chunk_ids=[]
    assert metrics.hit_rate == 1.0  # All 4 evaluable queries had at least one relevant hit
    assert metrics.mrr > 0.80  # Ranks: eval-01 (1), eval-02 (1/2), eval-03 (1), eval-04 (1) -> avg MRR ~ 0.875
    assert metrics.recall_at_k >= 0.80
    assert metrics.precision_at_k > 0.40


def test_rag_evaluator_comparative_baseline_ranking():
    # Verify that rank 1 match yields higher MRR than rank 3 match
    dataset = [
        EvaluationSample(
            id="q1",
            query="test",
            category="single_passage",
            expected_chunk_ids=["target"],
        )
    ]

    res_good = {
        "q1": [
            RetrievedChunk(
                chunk_id="target",
                document_id="d1",
                filename="f1",
                page_number=1,
                content="c",
                similarity_score=0.9,
            )
        ]
    }
    m_good = RAGEvaluator.evaluate_retrieval(res_good, dataset=dataset, k=3)

    res_delayed = {
        "q1": [
            RetrievedChunk(chunk_id="distractor1", document_id="d1", filename="f1", page_number=1, content="c", similarity_score=0.9),
            RetrievedChunk(chunk_id="distractor2", document_id="d1", filename="f1", page_number=1, content="c", similarity_score=0.8),
            RetrievedChunk(chunk_id="target", document_id="d1", filename="f1", page_number=1, content="c", similarity_score=0.7),
        ]
    }
    m_delayed = RAGEvaluator.evaluate_retrieval(res_delayed, dataset=dataset, k=3)

    assert m_good.mrr == 1.0
    assert m_delayed.mrr == pytest.approx(1.0 / 3.0, rel=1e-2)
    assert m_good.mrr > m_delayed.mrr
