from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Optional


DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/121.0.0.0 Safari/537.36"
)


@dataclass
class CrawlConfig:
    """Runtime configuration for the Finder.fi crawler."""

    output_dir: Path = Path("data/runs")
    headless: bool = True
    min_delay_seconds: float = 10.0
    max_delay_seconds: float = 20.0
    navigation_timeout_ms: int = 45_000
    user_agent: str = DEFAULT_USER_AGENT
    industries_filter: Optional[Iterable[str]] = None
    max_pages_per_industry: Optional[int] = None
    max_companies_per_industry: Optional[int] = None
    persist_raw_search: bool = False
    run_id: Optional[str] = None
    resume_from: Optional[Path] = None
    max_detail_retries: int = 3
    retry_backoff_seconds: float = 60.0
    failure_spike_threshold: int = 5
    failure_backoff_seconds: float = 300.0
    max_failure_breaks: int = 3

    def normalise(self) -> "CrawlConfig":
        self.output_dir = Path(self.output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        if self.min_delay_seconds > self.max_delay_seconds:
            self.min_delay_seconds, self.max_delay_seconds = (
                self.max_delay_seconds,
                self.min_delay_seconds,
            )
        self.max_detail_retries = max(1, int(self.max_detail_retries))
        self.retry_backoff_seconds = max(0.0, float(self.retry_backoff_seconds))
        self.failure_spike_threshold = max(1, int(self.failure_spike_threshold))
        self.failure_backoff_seconds = max(0.0, float(self.failure_backoff_seconds))
        self.max_failure_breaks = max(0, int(self.max_failure_breaks))
        return self


@dataclass
class RunMetadata:
    """Metadata describing a single crawl execution."""

    industries: list[str] = field(default_factory=list)
    total_companies: int = 0
    pages_visited: int = 0
    companies_written: int = 0
    failed_companies: int = 0

