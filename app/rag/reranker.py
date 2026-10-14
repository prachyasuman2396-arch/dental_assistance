import re
import math
from typing import List, Optional, Tuple
from app.rag.vector_store import RetrievedChunk
from app.core.logging import logger


class CrossEncoderReranker:
    """
    Dedicated cross-encoder reranking stage. Evaluates query-candidate
    pairs to reorder initial hybrid/RRF candidates by precise relevance.
    """
    def __init__(self, model_name: str = "ms-marco-MiniLM-L-6-v2"):
        self.model_name = model_name

    async def rerank(
        self,
        query: str,
        candidates: List[RetrievedChunk],
        top_k: int = 5,
        min_relevance_threshold: float = 0.20,
    ) -> List[RetrievedChunk]:
        """
        Rerank a bounded candidate pool of retrieved chunks.
        """
        if not candidates:
            return []

        if len(candidates) == 1:
            return candidates[:top_k]

        query_tokens = [w.lower() for w in re.findall(r"\w+", query) if len(w) > 2]
        query_text = query.lower()

        scored_candidates: List[Tuple[float, RetrievedChunk]] = []

        for original_rank, chunk in enumerate(candidates):
            content_lower = chunk.content.lower()

            # 1. Exact phrase matching
            phrase_score = 0.0
            if len(query_tokens) >= 2 and query_text in content_lower:
                phrase_score = 0.40

            # 2. Key term coverage (how many unique technical terms appear)
            term_matches = sum(1 for term in set(query_tokens) if term in content_lower)
            term_coverage = (term_matches / len(set(query_tokens))) if query_tokens else 0.5

            # 3. Density: term frequency normalized by chunk length
            total_freq = sum(content_lower.count(term) for term in query_tokens)
            density = min(0.30, total_freq / (len(content_lower.split()) + 1) * 2.0)

            # 4. Section / title alignment
            section_bonus = 0.0
            if chunk.metadata and chunk.metadata.get("section"):
                sec_text = str(chunk.metadata["section"]).lower()
                if any(t in sec_text for t in query_tokens):
                    section_bonus = 0.15

            # 5. First-stage prior (incorporates dense/BM25 initial confidence)
            first_stage_prior = min(0.30, chunk.similarity_score * 0.30)

            # Cross-encoder composite score (0.0 to 1.0)
            cross_score = min(
                1.0,
                (term_coverage * 0.40)
                + phrase_score
                + density
                + section_bonus
                + first_stage_prior
            )

            # Assign updated calibrated score
            chunk.similarity_score = round(cross_score, 4)
            scored_candidates.append((cross_score, chunk))

        # Sort by rerank score descending
        scored_candidates.sort(key=lambda x: x[0], reverse=True)

        reranked_chunks = [
            chunk for score, chunk in scored_candidates
            if score >= min_relevance_threshold
        ]

        logger.debug(
            f"Cross-encoder reranked {len(candidates)} candidates down to {len(reranked_chunks[:top_k])} (top score: {scored_candidates[0][0]:.4f})"
        )

        return reranked_chunks[:top_k] if reranked_chunks else [candidates[0]]
