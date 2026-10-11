import httpx
from typing import List, Optional
from app.core.config import settings
from app.core.logging import logger
from app.research.schemas import ResearchArticle, EvidenceLevel


class EuropePMCClient:
    """Europe PMC REST API client for biomedical literature and full-text abstracts."""

    def __init__(self, base_url: Optional[str] = None):
        self.base_url = base_url or settings.EUROPE_PMC_BASE_URL

    async def search(self, query: str, max_results: int = 5) -> List[ResearchArticle]:
        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                # Add dental domain restriction to search query
                enhanced_query = f"{query} AND (dental OR oral OR dentistry)"
                params = {
                    "query": enhanced_query,
                    "format": "json",
                    "pageSize": max_results,
                    "resultType": "core",
                    "sort": "P_PD_D desc",  # sort by publication date descending
                }

                url = f"{self.base_url}/search"
                res = await client.get(url, params=params)
                res.raise_for_status()
                data = res.json()

                result_list = data.get("resultList", {}).get("result", [])
                articles: List[ResearchArticle] = []

                for item in result_list:
                    title = item.get("title", "").strip().rstrip(".")
                    authors = item.get("authorString", "")
                    journal_info = item.get("journalInfo", {})
                    journal = journal_info.get("journal", {}).get("title", "")
                    pub_year = item.get("pubYear", "")
                    doi = item.get("doi")
                    pmid = item.get("pmid")
                    abstract = item.get("abstractText")

                    article_url = f"https://europepmc.org/article/MED/{pmid}" if pmid else (
                        f"https://doi.org/{doi}" if doi else None
                    )

                    # Deduce evidence level
                    pub_type = item.get("pubTypeList", {}).get("pubType", [])
                    evidence_level = EvidenceLevel.GENERAL
                    for pt in pub_type:
                        pt_lower = pt.lower()
                        if "systematic review" in pt_lower or "meta-analysis" in pt_lower:
                            evidence_level = EvidenceLevel.SYSTEMATIC_REVIEW
                            break
                        elif "guideline" in pt_lower:
                            evidence_level = EvidenceLevel.CLINICAL_GUIDELINE
                            break
                        elif "randomized" in pt_lower or "clinical trial" in pt_lower:
                            evidence_level = EvidenceLevel.RANDOMIZED_TRIAL
                            break

                    articles.append(
                        ResearchArticle(
                            title=title,
                            authors=authors,
                            journal=journal,
                            publication_date=pub_year,
                            doi=doi,
                            pmid=pmid,
                            url=article_url,
                            abstract=abstract,
                            source_type="europe_pmc",
                            evidence_level=evidence_level,
                        )
                    )

                return articles

            except Exception as e:
                logger.warning(f"Europe PMC search failed: {e}")
                return []
