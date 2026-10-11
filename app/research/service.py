import asyncio
import re
from typing import List, Optional
from app.core.config import settings
from app.core.logging import logger
from app.research.schemas import ResearchArticle, EvidenceLevel
from app.research.pubmed import PubMedClient
from app.research.europe_pmc import EuropePMCClient
from app.research.crossref import CrossrefClient
from app.research.web_search import WebSearchClient


class ResearchService:
    """
    Unified scholarly research service orchestrating PubMed, Europe PMC,
    Crossref, and web search with deduplication, ranking, and content sanitization.
    """
    def __init__(
        self,
        pubmed_client: Optional[PubMedClient] = None,
        europe_pmc_client: Optional[EuropePMCClient] = None,
        crossref_client: Optional[CrossrefClient] = None,
        web_client: Optional[WebSearchClient] = None,
    ):
        self.pubmed = pubmed_client or PubMedClient()
        self.europe_pmc = europe_pmc_client or EuropePMCClient()
        self.crossref = crossref_client or CrossrefClient()
        self.web = web_client or WebSearchClient()

    @staticmethod
    def sanitize_untrusted_text(text: Optional[str]) -> str:
        """
        Sanitize untrusted research text to prevent prompt injection or override attempts.
        Removes dangerous instruction-like sequences.
        """
        if not text:
            return ""

        # Remove attempts to inject system instructions or role overrides
        cleaned = re.sub(
            r"(?i)(ignore previous instructions|system\s*:|assistant\s*:|you must now)",
            "[REDACTED INSTRUCTION]",
            text,
        )
        return cleaned.strip()

    async def search_literature(
        self,
        query: str,
        max_results: int = settings.RESEARCH_MAX_RESULTS,
    ) -> List[ResearchArticle]:
        """
        Query biomedical repositories in parallel and return deduplicated, ranked research articles.
        """
        tasks = [
            self.pubmed.search(query, max_results=max_results),
            self.europe_pmc.search(query, max_results=max_results),
        ]

        if settings.TAVILY_API_KEY:
            tasks.append(self.web.search(query, max_results=max_results))
        else:
            tasks.append(self.crossref.search(query, max_results=max_results))

        results_lists = await asyncio.gather(*tasks, return_exceptions=True)

        all_articles: List[ResearchArticle] = []
        for res in results_lists:
            if isinstance(res, list):
                all_articles.extend(res)
            elif isinstance(res, Exception):
                logger.warning(f"Research provider query failed: {res}")

        # Deduplicate by PMID, DOI, and normalized title
        seen_identifiers = set()
        unique_articles: List[ResearchArticle] = []

        for art in all_articles:
            norm_title = re.sub(r"[^\w\s]", "", art.title.lower()).strip()[:60]
            identifier = art.pmid or art.doi or norm_title

            if identifier and identifier in seen_identifiers:
                continue
            seen_identifiers.add(identifier)

            # Sanitize title and abstract
            art.title = self.sanitize_untrusted_text(art.title)
            if art.abstract:
                art.abstract = self.sanitize_untrusted_text(art.abstract)

            unique_articles.append(art)

        # Priority ranking: Systematic reviews & Guidelines first, then by presence of abstract
        def rank_key(article: ResearchArticle) -> int:
            score = 0
            if article.evidence_level in (EvidenceLevel.SYSTEMATIC_REVIEW, EvidenceLevel.CLINICAL_GUIDELINE):
                score += 50
            elif article.evidence_level == EvidenceLevel.RANDOMIZED_TRIAL:
                score += 30
            if article.abstract:
                score += 20
            if article.pmid:
                score += 10
            return score

        unique_articles.sort(key=rank_key, reverse=True)
        return unique_articles[:max_results]
