# Finder.fi Industry Crawler

This project provides a stealthy web crawler that extracts industry and company information from [Finder.fi](https://www.finder.fi/toimialat). It leverages Playwright with headless Chromium to solve the AWS WAF JavaScript challenge and reads the structured `__NEXT_DATA__` payloads rendered by the site. The crawler is optimised for marathon-style runs that can span hours or days while staying below Cloudflare rate limits and while keeping progress checkpoints on disk.

## Features
- Discover industries via the `toimialat` index.
- Iterate paginated search results for each industry (15 results per page) with configurable limits and resumable checkpoints.
- Fetch detailed company profiles and persist combined search/detail data as JSON for downstream ELT ingestion.
- Built-in pacing controls (10–20 seconds between requests by default), optional industry filters, and headless/non-headless modes.
- Automatic run workspaces (`data/runs/<timestamp>/`) capturing logs, crawl metadata, and resumable progress state.

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
   JSON output will appear under `data/runs/<timestamp>/companies/<industry>/<company_name>_<business_id>.json` together with `state.json`, `run_metadata.json`, and log files under `logs/`.

3. Resume a run at any time by pointing the CLI to the previous workspace (absolute path or relative to `--output-root`):

   ```bash
   PYTHONPATH=src python -m finder_crawler.cli --resume data/runs/20240205_120000
   ```

   The crawler continues from the recorded page/index for each industry while skipping company detail requests that already exist on disk.

## Full dataset crawl

To crawl every available company across all Finder.fi industries in one continuous run, invoke the CLI with the `--full-run` flag. This clears any per-industry filters or page/company limits so the crawler keeps going until the catalog is exhausted:

```bash
PYTHONPATH=src python -m finder_crawler.cli --full-run --min-delay 12 --max-delay 28
```

* A new timestamped workspace (e.g. `data/runs/20240205_235959/`) is created automatically with logs, metadata, and resumable `state.json` checkpoints.
* If the process is interrupted, restart it with `--resume` pointing to the workspace directory to continue where it left off.
* Adjust the delay bounds to tune pacing for your environment—longer delays (e.g. 15–30 seconds) further reduce the likelihood of triggering Cloudflare rate limiting during a multi-day crawl.

Use `python -m finder_crawler.cli --help` to view all options.

> **Note:** Crawling the entire dataset still requires a significant number of requests (thousands per industry). Keep the generous default pacing or slow it down further with `--min-delay`/`--max-delay`, and consider distributing work across multiple days.

## Observability and resilience

- Every company write is logged to `logs/crawl.log`, including the Finder detail URL being fetched.
- Failed fetches are automatically retried up to three times with back-off; exhausted attempts are recorded in `logs/failed_companies.log` for later review.
- Output filenames combine a normalised company name and the Finder business identifier (e.g. `acme_oy_1234567-8.json`). Duplicate combinations receive a numeric suffix to stay unique.

