# Finder.fi Industry Crawler

This project provides a stealthy web crawler that extracts industry and company information from [Finder.fi](https://www.finder.fi/toimialat). It leverages Playwright with headless Chromium to solve the AWS WAF JavaScript challenge and reads the structured `__NEXT_DATA__` payloads rendered by the site.

## Features
- Discover industries via the `toimialat` index.
- Iterate paginated search results for each industry (15 results per page) with configurable limits.
- Fetch detailed company profiles and persist combined search/detail data as JSON for downstream ELT ingestion.
- Built-in pacing controls, optional industry filters, and headless/non-headless modes.

## Quick Start
1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   playwright install chromium
   ```
2. Run a sample crawl (single page per industry by default for safety):
   ```bash
   PYTHONPATH=src python -m finder_crawler.cli --industries Agentuuriliike --max-pages 1 --max-companies 3
   ```
   JSON output will appear under `data/output/<industry>/<company_id>.json` (a sample run is stored under `data/output_sample`).

Use `python -m finder_crawler.cli --help` to view all options.

> **Note:** Crawling the entire dataset requires a significant number of requests (thousands per industry). Adjust limits responsibly and consider pausing between runs to stay stealthy.

