from enum import Enum
from typing import Optional, List
from pydantic import BaseModel, Field


class EvidenceLevel(str, Enum):
    SYSTEMATIC_REVIEW = "Systematic Review / Meta-Analysis"
    CLINICAL_GUIDELINE = "Clinical Practice Guideline"
    RANDOMIZED_TRIAL = "Randomized Controlled Trial"
    COHORT_STUDY = "Cohort / Case-Control Study"
    CASE_REPORT = "Case Report / Series"
    IN_VITRO = "In Vitro / Laboratory Study"
    EXPERT_OPINION = "Review / Expert Opinion"
    GENERAL = "Educational / Web Resource"


class ResearchArticle(BaseModel):
    title: str
    authors: Optional[str] = None
    journal: Optional[str] = None
    publication_date: Optional[str] = None
    doi: Optional[str] = None
    pmid: Optional[str] = None
    url: Optional[str] = None
    abstract: Optional[str] = None
    source_type: str = "pubmed"  # pubmed, europe_pmc, crossref, web
    evidence_level: Optional[EvidenceLevel] = None

    def to_citation_str(self) -> str:
        parts = [self.title]
        if self.authors:
            parts.append(f"Authors: {self.authors}")
        if self.journal:
            parts.append(f"Journal: {self.journal}")
        if self.publication_date:
            parts.append(f"({self.publication_date})")
        if self.pmid:
            parts.append(f"PMID: {self.pmid}")
        if self.doi:
            parts.append(f"DOI: {self.doi}")
        if self.url:
            parts.append(f"URL: {self.url}")
        return " | ".join(parts)
