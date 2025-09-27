# Project Progress - Finder.fi Crawler

## Overview
- Goal: Build a stealthy web crawler that navigates https://www.finder.fi/toimialat, iterates through each industry, and extracts detailed company information into JSON files suitable for ELT pipelines.
- Constraints: Minimize requests, respect site structure, act stealthily (set headers, pacing, retry limits), and keep this document as the up-to-date source of truth.

## Current Status
- Identified AWS WAF JavaScript challenge on finder.fi that blocks simple HTTP clients; crawler must execute JS (headless browser needed).
- Playwright with headless Chromium selected to handle the WAF challenge; runtime dependencies installed via `playwright install-deps`.
- Confirmed industry index data is embedded in `__NEXT_DATA__` (alphabetized categories) and industry links map to search queries (`/search?what=<category>`).
- Discovered search result pages expose rich company data via `__NEXT_DATA__` with pagination controlled by `page` query parameter (15 results/page, >3k for Agentuuriliike) without direct DOM anchors.
- Verified company detail pages follow pattern `/Category/Name/City/yhteystiedot/<id>` and expose structured data in the company page `dehydratedState` payload.
- Implemented modular crawler (`BrowserSession`, `SearchCrawler`, `CompanyDetailFetcher`, `JsonStorage`, CLI) with configurable throttling and industry/page limits. Sample crawl writes JSON outputs combining search and detail payloads.

## Next Steps
1. Expand progress logging and documentation (README complete; ensure progress.md stays synced).
2. Optionally extend storage metadata (e.g., aggregated run manifest) if future iterations require.
3. Final verification: run lint/basic tests (CLI smoke test executed with 1 page/1 company) and prepare commit/PR summary.

