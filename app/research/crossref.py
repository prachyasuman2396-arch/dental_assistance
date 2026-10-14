import httpx
from typing import List, Optional
from app.core.config import settings
from app.core.logging import logger
from app.research.schemas import ResearchArticle, EvidenceLevel


class CrossrefClient:
    """Crossref API client for DOI resolution and scholarly publication metadata."""

    def __init__(self, base_url: Optional[str] = None):
        self.base_url = base_url or settings.CROSSREF_BASE_URL

    async def search(self, query: str, max_results: int = 5) -> List[ResearchArticle]:
        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                params = {
                    "query": query,
                    "rows": max_results,
                    "filter": "type:journal-article",
                }
                headers = {
                    "User-Agent": "StudentAIAssistant/1.0 (mailto:support@studentagent.edu)"
                }

                url = f"{self.base_url}/works"
                res = await client.get(url, params=params, headers=headers)
                res.raise_for_status()
                data = res.json()

                items = data.get("message", {}).get("items", [])
                articles: List[ResearchArticle] = []

                for item in items:
                    title_list = item.get("title", [])
                    title = title_list[0] if title_list else "Untitled"
                    
                    # Authors list
                    author_parts = []
                    for a in item.get("author", [])[:3]:
                        family = a.get("family", "")
                        given = a.get("given", "")
                        author_parts.append(f"{given} {family}".strip())
                    authors = ", ".join(author_parts) if author_parts else None

                    # Journal title
                    container = item.get("container-title", [])
                    journal = container[0] if container else None

                    # Date
                    date_parts = item.get("published", {}).get("date-parts", [[]])[0]
                    pub_date = str(date_parts[0]) if date_parts else None

                    doi = item.get("DOI")
                    url = f"https://doi.org/{doi}" if doi else item.get("URL")

                    articles.append(
                        ResearchArticle(
                            title=title,
                            authors=authors,
                            journal=journal,
                            publication_date=pub_date,
                            doi=doi,
                            pmid=None,
                            url=url,
                            abstract=None,
                            source_type="crossref",
                            evidence_level=EvidenceLevel.GENERAL,
                        )
                    )

                return articles

            except Exception as e:
                logger.warning(f"Crossref search failed: {e}")
                return []
