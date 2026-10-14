import re
from typing import List, Optional
from pydantic import BaseModel
from app.rag.vector_store import RetrievedChunk
from app.core.logging import logger


class SufficiencyEvaluation(BaseModel):
    is_sufficient: bool
    confidence_score: float
    missing_aspects: List[str] = []
    recommendation: str  # "proceed", "retry_broader", "insufficient_evidence"


class EvidenceSufficiencyChecker:
    """
    Dedicated evidence-sufficiency evaluation.
    Verifies that retrieved passages contain direct evidence to support
    an educational response, avoiding unsupported hallucination.
    """
    def __init__(
        self,
        min_term_coverage: float = 0.50,
        min_top_similarity: float = 0.30,
    ):
        self.min_term_coverage = min_term_coverage
        self.min_top_similarity = min_top_similarity

    def evaluate(self, query: str, retrieved_chunks: List[RetrievedChunk]) -> SufficiencyEvaluation:
        """Evaluate evidence coverage against student query."""
        if not retrieved_chunks:
            return SufficiencyEvaluation(
                is_sufficient=False,
                confidence_score=0.0,
                missing_aspects=["No relevant document passages found."],
                recommendation="insufficient_evidence",
            )

        query_tokens = [w.lower() for w in re.findall(r"\w+", query) if len(w) > 2]
        stopwords = {
            "what", "when", "where", "which", "who", "whom", "this", "that", "these",
            "those", "explain", "describe", "tell", "does", "have", "with", "from"
        }
        substantive_tokens = [t for t in query_tokens if t not in stopwords]

        if not substantive_tokens:
            return SufficiencyEvaluation(
                is_sufficient=True,
                confidence_score=0.85,
                recommendation="proceed",
            )

        # Concatenate all retrieved chunk texts
        corpus_text = " ".join(c.content.lower() for c in retrieved_chunks)

        missing_terms = [t for t in substantive_tokens if t not in corpus_text]
        coverage = 1.0 - (len(missing_terms) / len(substantive_tokens))

        top_similarity = max(c.similarity_score for c in retrieved_chunks)

        # Confidence is a blend of term coverage and top similarity score
        confidence = round((coverage * 0.6) + (min(1.0, top_similarity) * 0.4), 3)

        # Sufficient if term coverage is high and similarity is above minimum viable floor
        is_sufficient = (
            (coverage >= self.min_term_coverage and top_similarity >= self.min_top_similarity)
            or (coverage >= 0.75 and top_similarity >= 0.20)
        )

        if not is_sufficient:
            logger.info(
                f"Evidence insufficient: coverage={coverage:.2f}, top_sim={top_similarity:.2f}, missing={missing_terms}"
            )
            return SufficiencyEvaluation(
                is_sufficient=False,
                confidence_score=confidence,
                missing_aspects=missing_terms,
                recommendation="retry_broader" if coverage > 0.25 else "insufficient_evidence",
            )

        return SufficiencyEvaluation(
            is_sufficient=True,
            confidence_score=confidence,
            missing_aspects=[],
            recommendation="proceed",
        )
