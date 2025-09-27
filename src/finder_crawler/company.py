from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Optional

from .browser import BrowserSession
from .utils import build_company_detail_url


@dataclass
class CompanyDetail:
    industry: str
    company_id: str
    detail_url: str
    payload: Mapping[str, Any]


class CompanyDetailFetcher:
    def __init__(self, session: BrowserSession) -> None:
        self._session = session

    async def fetch(
        self,
        industry: str,
        company_id: str,
        company_name: str,
        city: Optional[str],
        category: str,
        *,
        detail_url: Optional[str] = None,
    ) -> CompanyDetail:
        url = detail_url or build_company_detail_url(category or industry, company_name, city, company_id)
        data = await self._session.goto(url)
        state = data["props"]["pageProps"]["dehydratedState"]["queries"][0]["state"]["data"]
        return CompanyDetail(
            industry=industry,
            company_id=company_id,
            detail_url=url,
            payload=state,
        )

