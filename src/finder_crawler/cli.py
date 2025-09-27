from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable

from .config import CrawlConfig
from .crawler import configure_logging, run


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Finder.fi industry/company crawler")
    parser.add_argument("--output-dir", type=Path, default=Path("data/output"), help="Directory for JSON output")
    parser.add_argument("--industries", nargs="*", help="Optional list of industry names to crawl (case-insensitive)")
    parser.add_argument("--max-pages", type=int, default=1, help="Maximum pages per industry (default: 1 for safety)")
    parser.add_argument("--max-companies", type=int, default=None, help="Optional cap on companies per industry")
    parser.add_argument("--headless", action=argparse.BooleanOptionalAction, default=True, help="Run browser in headless mode")
    parser.add_argument("--min-delay", type=float, default=1.5, help="Minimum delay between requests (seconds)")
    parser.add_argument("--max-delay", type=float, default=3.5, help="Maximum delay between requests (seconds)")
    parser.add_argument("--verbose", action="store_true", help="Enable debug logging")
    return parser.parse_args(argv)


def main(argv: Iterable[str] | None = None) -> None:
    args = parse_args(argv)
    configure_logging(args.verbose)
    config = CrawlConfig(
        output_dir=args.output_dir,
        headless=args.headless,
        min_delay_seconds=args.min_delay,
        max_delay_seconds=args.max_delay,
        industries_filter=args.industries or None,
        max_pages_per_industry=args.max_pages if args.max_pages and args.max_pages > 0 else None,
        max_companies_per_industry=args.max_companies if args.max_companies and args.max_companies > 0 else None,
    )
    result = run(config)
    print(
        "Crawl complete:",
        {
            "industries": result.industries,
            "companies": result.companies_written,
            "pages": result.pages_visited,
        },
    )


if __name__ == "__main__":
    main()

