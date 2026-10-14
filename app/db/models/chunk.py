import uuid
from typing import Optional, TYPE_CHECKING
from sqlalchemy import String, ForeignKey, Integer, Text, JSON, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from pgvector.sqlalchemy import Vector
from app.db.base import Base, TimestampMixin
from app.core.config import settings

if TYPE_CHECKING:
    from app.db.models.document import Document


class DocumentChunk(Base, TimestampMixin):
    __tablename__ = "document_chunks"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    document_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("documents.id", ondelete="CASCADE"), index=True, nullable=False
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), index=True, nullable=False)

    # Hierarchical and structure-aware RAG columns
    parent_chunk_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    section_title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    page_start: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    page_end: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    # pgvector embedding column
    embedding: Mapped[Optional[list]] = mapped_column(
        Vector(settings.EMBEDDING_DIMENSION), nullable=True
    )
    chunk_metadata: Mapped[Optional[dict]] = mapped_column(JSON, default=dict, nullable=True)

    document: Mapped["Document"] = relationship("Document", back_populates="chunks")

    __table_args__ = (
        Index("ix_doc_chunk_user_doc", "user_id", "document_id"),
        Index("ix_doc_chunks_parent_chunk_id", "parent_chunk_id"),
    )
