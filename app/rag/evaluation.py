from typing import List, Dict, Any, Optional
from pydantic import BaseModel
from app.rag.vector_store import RetrievedChunk


class EvaluationSample(BaseModel):
    id: str
    query: str
    category: str  # "single_passage", "multi_passage", "paraphrase", "technical_term", "insufficient_evidence"
    expected_chunk_ids: List[str]
    description: Optional[str] = None


class RetrievalEvaluationMetrics(BaseModel):
    precision_at_k: float
    recall_at_k: float
    mrr: float  # Mean Reciprocal Rank
    hit_rate: float
    total_queries: int


BENCHMARK_STUDENT_DATASET: List[EvaluationSample] = [
    EvaluationSample(
        id="eval-01",
        query="What is the biochemical function of ATP synthase during oxidative phosphorylation?",
        category="technical_term",
        expected_chunk_ids=["chk-atp-synthase-01"],
        description="Single-passage technical query on cellular bioenergetics",
    ),
    EvaluationSample(
        id="eval-02",
        query="How does CRISPR-Cas9 achieve targeted double-strand DNA cleavage?",
        category="single_passage",
        expected_chunk_ids=["chk-crispr-01"],
        description="Specific molecular mechanism question",
    ),
    EvaluationSample(
        id="eval-03",
        query="Compare the light-dependent and Calvin cycle stages of photosynthesis.",
        category="multi_passage",
        expected_chunk_ids=["chk-photo-light-01", "chk-photo-calvin-02"],
        description="Multi-passage comparative synthesis question",
    ),
    EvaluationSample(
        id="eval-04",
        query="Explain how mRNA vaccines stimulate memory B-cell and T-cell adaptive immunity.",
        category="paraphrase",
        expected_chunk_ids=["chk-mrna-immune-01"],
        description="Paraphrased immunology inquiry",
    ),
    EvaluationSample(
        id="eval-05",
        query="What was the exact warp speed calculation used by Albert Einstein in 1905?",
        category="insufficient_evidence",
        expected_chunk_ids=[],
        description="Negative test case with unanswerable evidence to verify sufficiency check",
    ),
]


class RAGEvaluator:
    """
    Offline evaluation framework for measuring IR metrics across
    dense, sparse, hybrid (RRF), and cross-encoder retrieval configurations.
    """

    @staticmethod
    def evaluate_retrieval(
        retrieved_results: Dict[str, List[RetrievedChunk]],  # sample_id -> List[RetrievedChunk]
        dataset: Optional[List[EvaluationSample]] = None,
        k: int = 5,
    ) -> RetrievalEvaluationMetrics:
        samples = dataset or BENCHMARK_STUDENT_DATASET
        evaluable_samples = [s for s in samples if s.expected_chunk_ids]

        if not evaluable_samples:
            return RetrievalEvaluationMetrics(
                precision_at_k=1.0,
                recall_at_k=1.0,
                mrr=1.0,
                hit_rate=1.0,
                total_queries=0,
            )

        total_precision = 0.0
        total_recall = 0.0
        total_reciprocal_rank = 0.0
        total_hits = 0

        for sample in evaluable_samples:
            retrieved = retrieved_results.get(sample.id, [])[:k]
            retrieved_ids = [c.chunk_id for c in retrieved]

            # Hits
            hits = [cid for cid in retrieved_ids if cid in sample.expected_chunk_ids]

            # Precision@k: fraction of retrieved chunks that are relevant
            precision = len(hits) / k if k > 0 else 0.0
            total_precision += precision

            # Recall@k: fraction of relevant chunks that are retrieved
            recall = len(hits) / len(sample.expected_chunk_ids) if sample.expected_chunk_ids else 0.0
            total_recall += recall

            # Hit Rate@k: at least 1 relevant chunk retrieved
            if hits:
                total_hits += 1

            # Reciprocal Rank: 1 / rank of first relevant chunk
            rr = 0.0
            for rank, cid in enumerate(retrieved_ids):
                if cid in sample.expected_chunk_ids:
                    rr = 1.0 / (rank + 1)
                    break
            total_reciprocal_rank += rr

        n = len(evaluable_samples)
        return RetrievalEvaluationMetrics(
            precision_at_k=round(total_precision / n, 4),
            recall_at_k=round(total_recall / n, 4),
            mrr=round(total_reciprocal_rank / n, 4),
            hit_rate=round(total_hits / n, 4),
            total_queries=n,
        )
