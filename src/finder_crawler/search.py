from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, AsyncIterator, Dict, List, Mapping, Optional
from urllib.parse import quote_plus

from .browser import BrowserSession
from .config import CrawlConfig


@dataclass
class SearchResult:
    """Container for company summary data from search results."""

    industry: str
    page_number: int
    index_on_page: int
    payload: Mapping[str, Any]
    query_info: Mapping[str, Any]

    @property
    def company_id(self) -> str:
        return str(self.payload.get("id") or self.payload.get("company", {}).get("id"))

    @property
    def company_name(self) -> str:
        return str(self.payload.get("name") or self.payload.get("company", {}).get("name"))

    @property
    def city(self) -> Optional[str]:
        return self.payload.get("cityName") or self.payload.get("company", {}).get("cityName")

    @property
    def category(self) -> str:
        return str(
            self.payload.get("mainSuperCategoryName")
            or self.payload.get("mainLineOfBusinessName")
            or self.industry
        )


class SearchCrawler:
    def __init__(self, session: BrowserSession, config: CrawlConfig) -> None:
        self._session = session
        self._config = config

    async def iterate_results(self, industry: str) -> AsyncIterator[SearchResult]:
        encoded = quote_plus(industry)
        page = 1
        total_pages = None
        yielded = 0

        while True:
            if self._config.max_pages_per_industry and page > self._config.max_pages_per_industry:
                break
            data = await self._session.goto(f"https://www.finder.fi/search?what={encoded}&page={page}")
            query_state = data["props"]["pageProps"]["dehydratedState"]["queries"][0]["state"]
            results: List[Mapping[str, Any]] = query_state["data"]["results"]
            query_info: Dict[str, Any] = dict(query_state["data"].get("query", {}))
            total_results = query_info.get("totalResults", len(results))
            per_page = query_info.get("resultsPerPage", len(results) or 1)
            if total_pages is None:
                total_pages = math.ceil(total_results / per_page) if per_page else 1

            for idx, payload in enumerate(results, start=1):
                if self._config.max_companies_per_industry and yielded >= self._config.max_companies_per_industry:
                    return
                yield SearchResult(
                    industry=industry,
                    page_number=page,
                    index_on_page=idx,
                    payload=payload,
                    query_info=query_info,
                )
                yielded += 1

            page += 1
            if total_pages and page > total_pages:
                break

