import httpx
from typing import List, Optional
from app.core.config import settings
from app.core.logging import logger
from app.research.schemas import ResearchArticle, EvidenceLevel


class PubMedClient:
    """NCBI PubMed E-utilities client for peer-reviewed scholarly literature."""

    BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.NCBI_API_KEY

    async def search(self, query: str, max_results: int = 5) -> List[ResearchArticle]:
        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                # 1. Search for PMIDs
                search_params = {
                    "db": "pubmed",
                    "term": query,
                    "retmode": "json",
                    "retmax": max_results,
                    "sort": "pub_date",
                }
                if self.api_key:
                    search_params["api_key"] = self.api_key

                search_res = await client.get(f"{self.BASE_URL}/esearch.fcgi", params=search_params)
                search_res.raise_for_status()
                search_data = search_res.json()

                id_list = search_data.get("esearchresult", {}).get("idlist", [])
                if not id_list:
                    return []

                # 2. Fetch document summaries
                summary_params = {
                    "db": "pubmed",
                    "id": ",".join(id_list),
                    "retmode": "json",
                }
                if self.api_key:
                    summary_params["api_key"] = self.api_key

                summary_res = await client.get(f"{self.BASE_URL}/esummary.fcgi", params=summary_params)
                summary_res.raise_for_status()
                summary_data = summary_res.json().get("result", {})

                articles: List[ResearchArticle] = []
                for pmid in id_list:
                    item = summary_data.get(pmid)
                    if not item:
                        continue

                    title = item.get("title", "").strip().rstrip(".")
                    authors = ", ".join([a.get("name", "") for a in item.get("authors", [])][:3])
                    journal = item.get("source", "")
                    pub_date = item.get("pubdate", "")
                    
                    # Extract DOI if present in articleids
                    doi = None
                    for aid in item.get("articleids", []):
                        if aid.get("idtype") == "doi":
                            doi = aid.get("value")
                            break

                    url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"

                    # Infer evidence level from pub types
                    pubtypes = [pt.lower() for pt in item.get("pubtype", [])]
                    evidence_level = EvidenceLevel.GENERAL
                    if any("systematic review" in pt or "meta-analysis" in pt for pt in pubtypes):
                        evidence_level = EvidenceLevel.SYSTEMATIC_REVIEW
                    elif any("guideline" in pt for pt in pubtypes):
                        evidence_level = EvidenceLevel.CLINICAL_GUIDELINE
                    elif any("clinical trial" in pt or "randomized" in pt for pt in pubtypes):
                        evidence_level = EvidenceLevel.RANDOMIZED_TRIAL
                    elif any("review" in pt for pt in pubtypes):
                        evidence_level = EvidenceLevel.EXPERT_OPINION

                    articles.append(
                        ResearchArticle(
                            title=title,
                            authors=authors,
                            journal=journal,
                            publication_date=pub_date,
                            doi=doi,
                            pmid=pmid,
                            url=url,
                            abstract=None,  # esummary does not return full abstract
                            source_type="pubmed",
                            evidence_level=evidence_level,
                        )
                    )

                return articles

            except Exception as e:
                logger.warning(f"PubMed search error: {e}")
                return []
