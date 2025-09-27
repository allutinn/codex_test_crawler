from __future__ import annotations

import asyncio
import logging

from .browser import BrowserSession
from .company import CompanyDetailFetcher
from .config import CrawlConfig, RunMetadata
from .industries import iter_industry_names
from .search import SearchCrawler
from .storage import CompanyRecord, JsonStorage
from .utils import timestamp_utc


logger = logging.getLogger(__name__)


async def run_crawl(config: CrawlConfig) -> RunMetadata:
    config = config.normalise()
    storage = JsonStorage(config)
    metadata = RunMetadata()

    async with BrowserSession(config) as session:
        industries = await iter_industry_names(session)
        if config.industries_filter:
            allowed = {name.lower() for name in config.industries_filter}
            industries = [name for name in industries if name.lower() in allowed]
        metadata.industries = industries

        search = SearchCrawler(session, config)
        details = CompanyDetailFetcher(session)

        for industry in industries:
            logger.info("Processing industry %s", industry)
            pages_seen = set()
            async for result in search.iterate_results(industry):
                pages_seen.add(result.page_number)
                company_id = result.company_id
                if not company_id:
                    logger.warning("Skipping result without company id: %s", result.payload)
                    continue
                try:
                    detail = await details.fetch(
                        industry=industry,
                        company_id=company_id,
                        company_name=result.company_name,
                        city=result.city,
                        category=result.category,
                    )
                except Exception as exc:  # pragma: no cover - network issues
                    logger.exception("Failed to fetch detail for %s: %s", company_id, exc)
                    continue

                record = CompanyRecord(
                    industry=industry,
                    company_id=company_id,
                    search_payload=result.payload,
                    detail_payload=detail.payload,
                    search_context={
                        "page": result.page_number,
                        "index_on_page": result.index_on_page,
                        "query": result.query_info,
                    },
                    metadata={
                        "fetched_at": timestamp_utc(),
                        "detail_url": detail.detail_url,
                        "industry": industry,
                    },
                )
                storage.write_company(record)
                metadata.companies_written += 1
            metadata.pages_visited += len(pages_seen)
    metadata.total_companies = metadata.companies_written
    return metadata


def configure_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")


def run(config: CrawlConfig) -> RunMetadata:
    return asyncio.run(run_crawl(config))

