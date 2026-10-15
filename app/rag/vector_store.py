from typing import List, Optional, Dict, Any
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from app.db.models.chunk import DocumentChunk
from app.db.models.document import Document
from app.rag.embeddings import BaseEmbeddingProvider, get_embedding_provider
from app.core.logging import logger


class RetrievedChunk(BaseModel):
    chunk_id: str
    document_id: str
    filename: str
    page_number: int
    content: str
    similarity_score: float
    metadata: Dict[str, Any] = {}
    parent_chunk_id: Optional[str] = None
    section_title: Optional[str] = None


class PgVectorRetriever:
    """
    pgvector semantic retrieval engine with user isolation,
    metadata filtering, and page citation tracking.
    """
    def __init__(
        self,
        session: AsyncSession,
        embedding_provider: Optional[BaseEmbeddingProvider] = None,
    ):
        self.session = session
        self.embedding_provider = embedding_provider or get_embedding_provider()

    async def similarity_search(
        self,
        query: str,
        user_id: str,
        document_id: Optional[str] = None,
        top_k: int = 5,
        min_similarity: float = 0.35,
    ) -> List[RetrievedChunk]:
        """
        Perform cosine distance similarity search on document_chunks table.
        Strictly filters by user_id to prevent cross-tenant data leaks.
        """
        # Generate query embedding
        query_vector = self.embedding_provider.embed_query(query)

        # Distance expression: DocumentChunk.embedding.cosine_distance(query_vector)
        # Cosine similarity = 1 - cosine_distance
        cosine_dist = DocumentChunk.embedding.cosine_distance(query_vector)

        # Build query joining with Document to fetch filename
        stmt = (
            select(
                DocumentChunk,
                Document.filename,
                cosine_dist.label("distance"),
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

        stmt = stmt.order_by(cosine_dist.asc()).limit(top_k * 2)

        try:
            results = await self.session.execute(stmt)
            rows = results.all()
        except Exception as e:
            logger.error(f"Vector search failed: {e}")
            return []

        chunks: List[RetrievedChunk] = []
        seen_texts = set()

        for chunk_obj, filename, distance in rows:
            dist_val = float(distance) if distance is not None else 1.0
            similarity = max(0.0, 1.0 - dist_val)

            if similarity < min_similarity:
                continue

            # Deduplicate near-identical snippets
            snippet_key = chunk_obj.content[:100]
            if snippet_key in seen_texts:
                continue
            seen_texts.add(snippet_key)

            p_id = getattr(chunk_obj, "parent_chunk_id", None)
            sec_t = getattr(chunk_obj, "section_title", None)

            chunks.append(
                RetrievedChunk(
                    chunk_id=chunk_obj.id,
                    document_id=chunk_obj.document_id,
                    filename=filename,
                    page_number=chunk_obj.page_number,
                    content=chunk_obj.content,
                    similarity_score=round(similarity, 4),
                    metadata=chunk_obj.chunk_metadata or {},
                    parent_chunk_id=p_id if isinstance(p_id, str) else None,
                    section_title=sec_t if isinstance(sec_t, str) else None,
                )
            )

            if len(chunks) >= top_k:
                break

        return chunks
