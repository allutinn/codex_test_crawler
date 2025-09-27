from __future__ import annotations

import asyncio
import logging
from collections import deque
from typing import Any, Mapping, Optional

from .browser import BrowserSession
from .company import CompanyDetailFetcher
from .config import CrawlConfig, RunMetadata
from .industries import iter_industry_names
from .search import SearchCrawler
from .state import RunState, RunWorkspace
from .storage import CompanyRecord, JsonStorage
from .utils import build_company_detail_url, timestamp_utc, write_json


logger = logging.getLogger(__name__)


class FailureTracker:
    """Track repeated failures and enforce back-off / abort semantics."""

    def __init__(self, threshold: int, backoff_seconds: float, max_breaks: int) -> None:
        self._threshold = max(1, threshold)
        self._backoff_seconds = max(0.0, backoff_seconds)
        self._max_breaks = max(0, max_breaks)
        self._recent: deque[str] = deque(maxlen=self._threshold)
        self.total_failures = 0
        self._breaks_taken = 0

    def record_success(self) -> None:
        self._recent.clear()

    async def record_failure(self, company_key: str) -> bool:
        """Register a failure and decide whether the crawl may continue.

        Returns ``False`` when the crawl should be halted because repeated
        failures persisted through the configured number of back-off cycles.
        """

        self.total_failures += 1
        self._recent.append(company_key)
        if len(self._recent) < self._threshold:
            return True
        if len(set(self._recent)) <= 1:
            return True
        if self._breaks_taken >= self._max_breaks:
            return False

        logger.warning(
            "Multiple distinct failures detected (%s). Sleeping for %.1f seconds before retrying",
            list(self._recent),
            self._backoff_seconds,
        )
        if self._backoff_seconds:
            await asyncio.sleep(self._backoff_seconds)
        self._breaks_taken += 1
        self._recent.clear()
        return True


def extract_business_id(payload: Mapping[str, Any]) -> Optional[str]:
    """Attempt to extract the Finder business identifier from the payload."""

    candidates: list[Mapping[str, Any]] = []
    for key in ("aiProfile", "company", "basicInformation", "basicInfo"):
        section = payload.get(key)
        if isinstance(section, Mapping):
            candidates.append(section)
    candidates.append(payload)
    for section in candidates:
        for key in ("businessId", "business_id", "yTunnus", "y_tunnus"):
            value = section.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return None


async def run_crawl(config: CrawlConfig) -> RunMetadata:
    config = config.normalise()
    workspace = RunWorkspace.prepare(config.output_dir, config.run_id, config.resume_from)
    config.output_dir = workspace.companies_dir
    storage = JsonStorage(config)
    state = RunState.load(workspace.state_path) if workspace.is_resume else RunState(run_id=workspace.run_id)
    metadata = RunMetadata()
    failure_tracker = FailureTracker(
        config.failure_spike_threshold,
        config.failure_backoff_seconds,
        config.max_failure_breaks,
    )

    file_handler = logging.FileHandler(workspace.logs_dir / "crawl.log")
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    )
    root_logger = logging.getLogger()
    root_logger.addHandler(file_handler)

    logger.info("Starting crawl run %s (resume=%s)", workspace.run_id, workspace.is_resume)

    try:
        async with BrowserSession(config) as session:
            industries = await iter_industry_names(session)
            if config.industries_filter:
                allowed = {name.lower() for name in config.industries_filter}
                industries = [name for name in industries if name.lower() in allowed]
            state.ensure_industries(industries)
            state.save(workspace.state_path)
            metadata.industries = list(state.industries.keys())

            search = SearchCrawler(session, config)
            details = CompanyDetailFetcher(session)
            failure_log_path = workspace.logs_dir / "failed_companies.log"
            stop_requested = False

            for industry in state.remaining_industries():
                if stop_requested:
                    break
                progress = state.industry_progress(industry)
                logger.info(
                    "Processing industry %s (starting page %s index %s)",
                    industry,
                    progress.next_page,
                    progress.next_index,
                )
                current_page = None
                async for result in search.iterate_results(
                    industry,
                    start_page=progress.next_page,
                    start_index=progress.next_index,
                ):
                    if stop_requested:
                        break
                    if current_page != result.page_number:
                        if current_page is not None:
                            state.mark_page_complete(industry, current_page)
                        current_page = result.page_number
                        state.record_page_visit(industry, current_page)
                        metadata.pages_visited = state.total_pages_visited

                    company_id = result.company_id
                    if not company_id:
                        logger.warning("Skipping result without company id: %s", result.payload)
                        state.record_company(
                            industry,
                            result.page_number,
                            result.index_on_page,
                            None,
                            wrote_to_storage=False,
                        )
                        state.save(workspace.state_path)
                        failure_tracker.record_success()
                        continue

                    if storage.company_exists(industry, company_id):
                        logger.debug(
                            "Company %s already stored, skipping detail fetch",
                            company_id,
                        )
                        state.record_company(
                            industry,
                            result.page_number,
                            result.index_on_page,
                            company_id,
                            wrote_to_storage=False,
                        )
                        state.save(workspace.state_path)
                        failure_tracker.record_success()
                        continue

                    detail_url = build_company_detail_url(
                        result.category or industry,
                        result.company_name,
                        result.city,
                        company_id,
                    )
                    logger.info(
                        "Crawling company '%s' (%s) from %s page %s index %s -> %s",
                        result.company_name,
                        company_id,
                        industry,
                        result.page_number,
                        result.index_on_page,
                        detail_url,
                    )

                    detail = None
                    last_exception: Optional[Exception] = None
                    for attempt in range(1, config.max_detail_retries + 1):
                        try:
                            detail = await details.fetch(
                                industry=industry,
                                company_id=company_id,
                                company_name=result.company_name,
                                city=result.city,
                                category=result.category,
                                detail_url=detail_url,
                            )
                            failure_tracker.record_success()
                            break
                        except Exception as exc:  # pragma: no cover - network issues
                            last_exception = exc
                            logger.exception(
                                "Attempt %s/%s failed for %s (%s)",
                                attempt,
                                config.max_detail_retries,
                                company_id,
                                detail_url,
                            )
                            if attempt < config.max_detail_retries and config.retry_backoff_seconds:
                                await asyncio.sleep(config.retry_backoff_seconds)

                    if detail is None:
                        logger.error(
                            "Failed to fetch detail for %s after %s attempts", 
                            company_id,
                            config.max_detail_retries,
                        )
                        failure_line = (
                            f"{timestamp_utc()} | industry={industry} | page={result.page_number} | "
                            f"index={result.index_on_page} | company_id={company_id} | "
                            f"detail_url={detail_url} | error={last_exception!r}"
                        )
                        with failure_log_path.open("a", encoding="utf-8") as failure_handle:
                            failure_handle.write(failure_line + "\n")
                        state.record_company(
                            industry,
                            result.page_number,
                            result.index_on_page,
                            company_id,
                            wrote_to_storage=False,
                        )
                        state.save(workspace.state_path)
                        should_continue = await failure_tracker.record_failure(company_id)
                        if not should_continue:
                            logger.error(
                                "Stopping crawl after repeated failures. See %s for details.",
                                failure_log_path,
                            )
                            stop_requested = True
                            break
                        continue

                    business_id = extract_business_id(detail.payload)
                    if not business_id:
                        business_id = extract_business_id(result.payload)
                    storage_id = storage.make_storage_id(
                        industry,
                        result.company_name,
                        business_id,
                    )
                    crawled_at = timestamp_utc()
                    record = CompanyRecord(
                        industry=industry,
                        company_id=company_id,
                        storage_id=storage_id,
                        search_payload=result.payload,
                        detail_payload=detail.payload,
                        search_context={
                            "page": result.page_number,
                            "index_on_page": result.index_on_page,
                            "query": result.query_info,
                        },
                        metadata={
                            "industry": industry,
                            "company_name": result.company_name,
                            "business_id": business_id,
                            "storage_id": storage_id,
                            "crawled_at": crawled_at,
                            "crawled_url": detail.detail_url,
                        },
                    )
                    storage.write_company(record)
                    metadata.companies_written += 1
                    state.record_company(
                        industry,
                        result.page_number,
                        result.index_on_page,
                        company_id,
                        wrote_to_storage=True,
                    )
                    state.save(workspace.state_path)

                if stop_requested:
                    break
                if current_page is not None:
                    state.mark_page_complete(industry, current_page)
                state.mark_industry_complete(industry)
                state.save(workspace.state_path)

        metadata.total_companies = state.total_companies_written
        metadata.pages_visited = state.total_pages_visited
        metadata.failed_companies = failure_tracker.total_failures
        write_json(
            workspace.metadata_path,
            {
                "run_id": workspace.run_id,
                "industries": metadata.industries,
                "companies_written": metadata.companies_written,
                "pages_visited": metadata.pages_visited,
                "total_companies": metadata.total_companies,
                "failed_companies": metadata.failed_companies,
                "updated_at": timestamp_utc(),
            },
        )
        return metadata
    finally:
        root_logger.removeHandler(file_handler)
        file_handler.close()


def configure_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")


def run(config: CrawlConfig) -> RunMetadata:
    return asyncio.run(run_crawl(config))

