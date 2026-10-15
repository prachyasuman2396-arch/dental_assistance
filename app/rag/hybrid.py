import re
import time
import asyncio
import hashlib
from typing import List, Optional, Dict, Any, Tuple
from collections import OrderedDict
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from app.db.models.chunk import DocumentChunk
from app.db.models.document import Document
from app.rag.vector_store import PgVectorRetriever, RetrievedChunk
from app.rag.reranker import CrossEncoderReranker
from app.rag.compression import ContextCompressor
from app.rag.sufficiency import EvidenceSufficiencyChecker, SufficiencyEvaluation
from app.core.logging import logger

try:
    from rank_bm25 import BM25Okapi
except ImportError:
    BM25Okapi = None


def _tokenize(text: str) -> List[str]:
    """Alphanumeric tokenizer for BM25 and lexical search."""
    return re.findall(r"\w+", text.lower())


class RetrievalMetrics(BaseModel):
    dense_latency_ms: float = 0.0
    sparse_latency_ms: float = 0.0
    rrf_latency_ms: float = 0.0
    rerank_latency_ms: float = 0.0
    total_retrieval_ms: float = 0.0
    dense_candidate_count: int = 0
    sparse_candidate_count: int = 0
    fused_candidate_count: int = 0
    final_evidence_count: int = 0
    was_cached: bool = False
    recovery_attempted: bool = False


class RetrievalCache:
    """In-memory LRU cache for frequent query results."""
    def __init__(self, capacity: int = 500):
        self.capacity = capacity
        self.cache: OrderedDict[str, List[RetrievedChunk]] = OrderedDict()

    def make_key(self, user_id: str, query: str, doc_id: Optional[str], top_k: int) -> str:
        raw = f"{user_id}:{doc_id or '*'}:{query.strip().lower()}:{top_k}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def get(self, key: str) -> Optional[List[RetrievedChunk]]:
        if key in self.cache:
            self.cache.move_to_end(key)
            return self.cache[key]
        return None

    def put(self, key: str, chunks: List[RetrievedChunk]) -> None:
        if key in self.cache:
            self.cache.move_to_end(key)
        else:
            if len(self.cache) >= self.capacity:
                self.cache.popitem(last=False)
            self.cache[key] = chunks


_GLOBAL_RETRIEVAL_CACHE = RetrievalCache(capacity=500)


class HybridRetriever:
    """
    Production-grade multi-stage hybrid retrieval engine:
    1. Concurrent dense vector search (pgvector) + sparse BM25 search
    2. Reciprocal Rank Fusion (RRF)
    3. Cross-Encoder reranking
    4. Contextual compression
    5. Evidence sufficiency verification & bounded recovery retrieval
    """
    def __init__(
        self,
        session: AsyncSession,
        vector_retriever: Optional[PgVectorRetriever] = None,
        reranker: Optional[CrossEncoderReranker] = None,
        compressor: Optional[ContextCompressor] = None,
        sufficiency_checker: Optional[EvidenceSufficiencyChecker] = None,
    ):
        self.session = session
        self.vector_retriever = vector_retriever or PgVectorRetriever(session=session)
        self.reranker = reranker or CrossEncoderReranker()
        self.compressor = compressor or ContextCompressor()
        self.sufficiency_checker = sufficiency_checker or EvidenceSufficiencyChecker()
        self.cache = _GLOBAL_RETRIEVAL_CACHE

    async def retrieve(
        self,
        query: str,
        user_id: str,
        document_id: Optional[str] = None,
        top_k: int = 5,
        vector_weight: float = 0.6,
        bm25_weight: float = 0.4,
        rrf_k: int = 60,
        enable_reranking: bool = True,
        enable_compression: bool = True,
        enable_parent_expansion: bool = True,
    ) -> List[RetrievedChunk]:
        """
        High-level retrieval interface matching Graph Nodes signature.
        Executes parallel dense + BM25, RRF fusion, reranking, parent expansion, and compression.
        """
        chunks, _metrics, _evaluation = await self.pipeline_retrieve(
            query=query,
            user_id=user_id,
            document_id=document_id,
            top_k=top_k,
            vector_weight=vector_weight,
            bm25_weight=bm25_weight,
            rrf_k=rrf_k,
            enable_reranking=enable_reranking,
            enable_compression=enable_compression,
            enable_parent_expansion=enable_parent_expansion,
        )
        return chunks

    async def pipeline_retrieve(
        self,
        query: str,
        user_id: str,
        document_id: Optional[str] = None,
        top_k: int = 5,
        vector_weight: float = 0.6,
        bm25_weight: float = 0.4,
        rrf_k: int = 60,
        enable_reranking: bool = True,
        enable_compression: bool = True,
        enable_parent_expansion: bool = True,
        allow_recovery: bool = True,
    ) -> Tuple[List[RetrievedChunk], RetrievalMetrics, SufficiencyEvaluation]:
        """
        Full multi-stage retrieval pipeline with operational telemetry
        and bounded recovery loop.
        """
        start_time = time.perf_counter()
        metrics = RetrievalMetrics()

        # 0. Check retrieval cache
        cache_key = self.cache.make_key(user_id, query, document_id, top_k)
        cached_results = self.cache.get(cache_key)
        if cached_results is not None:
            metrics.was_cached = True
            metrics.final_evidence_count = len(cached_results)
            metrics.total_retrieval_ms = (time.perf_counter() - start_time) * 1000.0
            evaluation = self.sufficiency_checker.evaluate(query, cached_results)
            return cached_results, metrics, evaluation

        # 1. Parallel Dense & Sparse Retrieval
        t_dense_start = time.perf_counter()
        dense_task = self.vector_retriever.similarity_search(
            query=query,
            user_id=user_id,
            document_id=document_id,
            top_k=top_k * 3,
            min_similarity=0.20,
        )
        sparse_task = self._bm25_search(
            query=query,
            user_id=user_id,
            document_id=document_id,
            limit=top_k * 3,
        )

        dense_results, sparse_results = await asyncio.gather(dense_task, sparse_task)
        t_retrieval_end = time.perf_counter()

        metrics.dense_latency_ms = (t_retrieval_end - t_dense_start) * 1000.0
        metrics.sparse_latency_ms = (t_retrieval_end - t_dense_start) * 1000.0
        metrics.dense_candidate_count = len(dense_results)
        metrics.sparse_candidate_count = len(sparse_results)

        # 2. Reciprocal Rank Fusion (RRF)
        t_rrf_start = time.perf_counter()
        fused_candidates = self._reciprocal_rank_fusion(
            dense_results=dense_results,
            sparse_results=sparse_results,
            vector_weight=vector_weight,
            bm25_weight=bm25_weight,
            rrf_k=rrf_k,
            pool_size=top_k * 3,
        )
        metrics.rrf_latency_ms = (time.perf_counter() - t_rrf_start) * 1000.0
        metrics.fused_candidate_count = len(fused_candidates)

        # 3. Cross-Encoder Reranking
        candidates_to_rerank = fused_candidates
        if enable_reranking and fused_candidates:
            t_rerank_start = time.perf_counter()
            reranked = await self.reranker.rerank(
                query=query,
                candidates=fused_candidates,
                top_k=top_k,
            )
            metrics.rerank_latency_ms = (time.perf_counter() - t_rerank_start) * 1000.0
            candidates_to_rerank = reranked

        selected_candidates = candidates_to_rerank[:top_k]

        # 3b. Parent-child context expansion
        if enable_parent_expansion and selected_candidates:
            selected_candidates = await self._expand_parent_context(selected_candidates, user_id)

        # 4. Contextual Compression
        final_evidence = selected_candidates
        if enable_compression and selected_candidates:
            final_evidence = self.compressor.compress_candidates(query, selected_candidates)

        # 5. Evidence Sufficiency Verification
        evaluation = self.sufficiency_checker.evaluate(query, final_evidence)

        # 6. Bounded Recovery Loop (at most 1 retry if evidence insufficient)
        if not evaluation.is_sufficient and allow_recovery and evaluation.recommendation == "retry_broader":
            logger.info("Triggering bounded recovery retrieval with broadened query terms...")
            metrics.recovery_attempted = True
            broadened_query = f"{query} {' '.join(evaluation.missing_aspects)}"
            recovered_evidence, _, recovered_eval = await self.pipeline_retrieve(
                query=broadened_query,
                user_id=user_id,
                document_id=document_id,
                top_k=top_k,
                vector_weight=0.5,
                bm25_weight=0.5,
                rrf_k=40,
                enable_reranking=True,
                enable_compression=True,
                allow_recovery=False,  # strictly prevent recursive recovery loops
            )
            if len(recovered_evidence) > len(final_evidence) or recovered_eval.confidence_score > evaluation.confidence_score:
                final_evidence = recovered_evidence
                evaluation = recovered_eval

        metrics.final_evidence_count = len(final_evidence)
        metrics.total_retrieval_ms = (time.perf_counter() - start_time) * 1000.0

        # Save to retrieval cache
        if final_evidence:
            self.cache.put(cache_key, final_evidence)

        return final_evidence, metrics, evaluation

    def _reciprocal_rank_fusion(
        self,
        dense_results: List[RetrievedChunk],
        sparse_results: List[RetrievedChunk],
        vector_weight: float = 0.6,
        bm25_weight: float = 0.4,
        rrf_k: int = 60,
        pool_size: int = 15,
    ) -> List[RetrievedChunk]:
        """Combine dense and sparse candidate rankings with Reciprocal Rank Fusion."""
        chunk_map: Dict[str, RetrievedChunk] = {}
        rrf_scores: Dict[str, float] = {}

        for rank, chunk in enumerate(dense_results):
            chunk_map[chunk.chunk_id] = chunk
            rrf_scores[chunk.chunk_id] = rrf_scores.get(chunk.chunk_id, 0.0) + (
                vector_weight / (rrf_k + rank + 1)
            )

        for rank, chunk in enumerate(sparse_results):
            if chunk.chunk_id not in chunk_map:
                chunk_map[chunk.chunk_id] = chunk
            rrf_scores[chunk.chunk_id] = rrf_scores.get(chunk.chunk_id, 0.0) + (
                bm25_weight / (rrf_k + rank + 1)
            )

        sorted_chunk_ids = sorted(rrf_scores.keys(), key=lambda cid: rrf_scores[cid], reverse=True)

        fused_results: List[RetrievedChunk] = []
        seen_snippets = set()

        for cid in sorted_chunk_ids:
            chunk = chunk_map[cid]
            snippet_key = chunk.content[:120].strip()
            if snippet_key in seen_snippets:
                continue
            seen_snippets.add(snippet_key)

            fused_score = min(1.0, round(rrf_scores[cid] * (rrf_k / 2.0), 4))
            chunk.similarity_score = fused_score
            fused_results.append(chunk)

            if len(fused_results) >= pool_size:
                break

        return fused_results

    async def _bm25_search(
        self,
        query: str,
        user_id: str,
        document_id: Optional[str] = None,
        limit: int = 15,
    ) -> List[RetrievedChunk]:
        """Fetch candidate document chunks and rank them using BM25."""
        if BM25Okapi is None:
            return []

        query_tokens = _tokenize(query)
        if not query_tokens:
            return []

        stmt = (
            select(
                DocumentChunk,
                Document.filename,
            )
            .join(Document, Document.id == DocumentChunk.document_id)
            .where(
                and_(
                    DocumentChunk.user_id == user_id,
                    Document.user_id == user_id,
                )
            )
        )
        if document_id:
            stmt = stmt.where(DocumentChunk.document_id == document_id)

        stmt = stmt.limit(100)

        try:
            res = await self.session.execute(stmt)
            rows = res.all()
        except Exception as e:
            logger.warning(f"BM25 candidate query failed: {e}")
            return []

        if not rows:
            return []

        corpus = [_tokenize(chunk.content) for chunk, _ in rows]
        bm25 = BM25Okapi(corpus)
        scores = bm25.get_scores(query_tokens)

        scored_rows = []
        for idx, (chunk_obj, filename) in enumerate(rows):
            score = float(scores[idx])
            if score > 0.0:
                scored_rows.append((score, chunk_obj, filename))

        scored_rows.sort(key=lambda x: x[0], reverse=True)

        results: List[RetrievedChunk] = []
        max_score = scored_rows[0][0] if scored_rows else 1.0

        for score, chunk_obj, filename in scored_rows[:limit]:
            normalized_score = round(score / max_score, 4) if max_score > 0 else 0.0
            p_id = getattr(chunk_obj, "parent_chunk_id", None)
            sec_t = getattr(chunk_obj, "section_title", None)
            results.append(
                RetrievedChunk(
                    chunk_id=chunk_obj.id,
                    document_id=chunk_obj.document_id,
                    filename=filename,
                    page_number=chunk_obj.page_number,
                    content=chunk_obj.content,
                    similarity_score=normalized_score,
                    metadata=chunk_obj.chunk_metadata or {},
                    parent_chunk_id=p_id if isinstance(p_id, str) else None,
                    section_title=sec_t if isinstance(sec_t, str) else None,
                )
            )

        return results

    async def _expand_parent_context(
        self,
        candidates: List[RetrievedChunk],
        user_id: str,
    ) -> List[RetrievedChunk]:
        """
        Parent-child retrieval context expansion:
        If a retrieved chunk has a parent_chunk_id, fetch the surrounding parent
        chunk to supply complete structural context for grounded answer synthesis.
        """
        parent_ids = list({c.parent_chunk_id for c in candidates if c.parent_chunk_id})
        if not parent_ids:
            return candidates

        try:
            stmt = select(DocumentChunk).where(
                and_(
                    DocumentChunk.id.in_(parent_ids),
                    DocumentChunk.user_id == user_id,
                )
            )
            res = await self.session.execute(stmt)
            parent_chunks = {p.id: p.content for p in res.scalars().all()}
        except Exception as e:
            logger.debug(f"Parent chunk expansion lookup failed: {e}")
            return candidates

        expanded: List[RetrievedChunk] = []
        for c in candidates:
            if c.parent_chunk_id and c.parent_chunk_id in parent_chunks:
                parent_text = parent_chunks[c.parent_chunk_id]
                c_copy = c.model_copy()
                c_copy.content = f"{parent_text}\n\n[Matching Granular Passage: {c.content}]"
                expanded.append(c_copy)
            else:
                expanded.append(c)

        return expanded
