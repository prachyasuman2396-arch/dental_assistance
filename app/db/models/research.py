import uuid
from typing import Optional
from sqlalchemy import String, Text, Index
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base, TimestampMixin


class ResearchSource(Base, TimestampMixin):
    __tablename__ = "research_sources"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    query: Mapped[str] = mapped_column(String(512), index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(1024), nullable=False)
    authors: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    journal: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    publication_date: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    doi: Mapped[Optional[str]] = mapped_column(String(255), index=True, nullable=True)
    pmid: Mapped[Optional[str]] = mapped_column(String(100), index=True, nullable=True)
    url: Mapped[Optional[str]] = mapped_column(String(2048), nullable=True)
    abstract: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source_type: Mapped[str] = mapped_column(
        String(50), default="pubmed", nullable=False
    )  # pubmed, europe_pmc, crossref, web
    evidence_level: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True
    )  # Systematic Review, RCT, Clinical Guideline, In Vitro, etc.

    __table_args__ = (
        Index("ix_research_doi_pmid", "doi", "pmid"),
    )
