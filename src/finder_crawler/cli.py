from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable

from .config import CrawlConfig
from .crawler import configure_logging, run


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Finder.fi industry/company crawler")
    parser.add_argument(
        "--output-root",
        "--output-dir",
        dest="output_root",
        type=Path,
        default=Path("data/runs"),
        help="Base directory where timestamped crawl runs will be stored",
    )
    parser.add_argument("--industries", nargs="*", help="Optional list of industry names to crawl (case-insensitive)")
    parser.add_argument("--max-pages", type=int, default=None, help="Maximum pages per industry (default: crawl all)")
    parser.add_argument("--max-companies", type=int, default=None, help="Optional cap on companies per industry")
    parser.add_argument("--headless", action=argparse.BooleanOptionalAction, default=True, help="Run browser in headless mode")
    parser.add_argument("--min-delay", type=float, default=10.0, help="Minimum delay between requests (seconds)")
    parser.add_argument("--max-delay", type=float, default=20.0, help="Maximum delay between requests (seconds)")
    parser.add_argument("--run-id", type=str, default=None, help="Optional custom identifier for the crawl run directory")
    parser.add_argument(
        "--resume",
        type=Path,
        default=None,
        help="Resume from an existing run directory (absolute or relative to output root)",
    )
    parser.add_argument(
        "--full-run",
        action="store_true",
        help=(
            "Ignore industry/page/company limits and crawl the complete Finder.fi dataset in a single run"
        ),
    )
    parser.add_argument("--verbose", action="store_true", help="Enable debug logging")
    return parser.parse_args(argv)


def main(argv: Iterable[str] | None = None) -> None:
    args = parse_args(argv)
    configure_logging(args.verbose)
    industries_filter = args.industries or None
    max_pages = args.max_pages if args.max_pages and args.max_pages > 0 else None
    max_companies = (
        args.max_companies if args.max_companies and args.max_companies > 0 else None
    )

    if args.full_run:
        industries_filter = None
        max_pages = None
        max_companies = None

    config = CrawlConfig(
        output_dir=args.output_root,
        headless=args.headless,
        min_delay_seconds=args.min_delay,
        max_delay_seconds=args.max_delay,
        industries_filter=industries_filter,
        max_pages_per_industry=max_pages,
        max_companies_per_industry=max_companies,
        run_id=args.run_id,
        resume_from=args.resume,
    )
    result = run(config)
    print(
        "Crawl complete:",
        {
            "industries": result.industries,
            "companies": result.companies_written,
            "pages": result.pages_visited,
            "failed": result.failed_companies,
        },
    )


if __name__ == "__main__":
    main()

