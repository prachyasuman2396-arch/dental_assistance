import httpx
from typing import List, Optional
from app.core.config import settings
from app.core.logging import logger
from app.research.schemas import ResearchArticle, EvidenceLevel


class WebSearchClient:
    """Web search adapter supporting Tavily or general biomedical web search."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.TAVILY_API_KEY

    async def search(self, query: str, max_results: int = 5) -> List[ResearchArticle]:
        if not self.api_key:
            return []

        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                payload = {
                    "api_key": self.api_key,
                    "query": query,
                    "search_depth": "advanced",
                    "include_answer": False,
                    "max_results": max_results,
                }
                res = await client.post("https://api.tavily.com/search", json=payload)
                res.raise_for_status()
                data = res.json()

                results = data.get("results", [])
                articles: List[ResearchArticle] = []

                for item in results:
                    title = item.get("title", "")
                    url = item.get("url", "")
                    content = item.get("content", "")

                    evidence_level = EvidenceLevel.GENERAL
                    if "guideline" in url.lower() or "guideline" in title.lower():
                        evidence_level = EvidenceLevel.CLINICAL_GUIDELINE

                    articles.append(
                        ResearchArticle(
                            title=title,
                            authors="Web Source / Organization",
                            journal="Web Publication",
                            publication_date=None,
                            doi=None,
                            pmid=None,
                            url=url,
                            abstract=content,
                            source_type="web",
                            evidence_level=evidence_level,
                        )
                    )

                return articles

            except Exception as e:
                logger.warning(f"Tavily web search error: {e}")
                return []
