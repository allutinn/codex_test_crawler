from __future__ import annotations

import asyncio
import json
import random
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping
from urllib.parse import quote, quote_plus

from playwright.async_api import Page


async def random_delay(min_seconds: float, max_seconds: float) -> None:
    """Sleep for a random interval between the provided bounds."""

    await asyncio.sleep(random.uniform(min_seconds, max_seconds))


def ensure_directory(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def timestamp_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def slugify_path_segment(value: str) -> str:
    return quote(value.strip().replace(" ", " "), safe="")


def build_company_detail_url(category: str, name: str, city: str | None, company_id: str) -> str:
    city_segment = quote_plus(city) if city else ""
    return (
        f"https://www.finder.fi/{quote(category)}"
        f"/{quote_plus(name)}"
        f"/{city_segment if city_segment else 'yhteystiedot'}"
        f"/yhteystiedot/{company_id}"
    )


async def extract_next_data(page: Page) -> Mapping[str, Any]:
    """Return the Next.js bootstrap data from the current page."""

    data = await page.evaluate("window.__NEXT_DATA__")
    if not isinstance(data, Mapping):
        raise ValueError("Unexpected __NEXT_DATA__ payload")
    return data


def serialise_json(data: Mapping[str, Any] | Iterable[Any]) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True)


def write_json(path: Path, payload: Mapping[str, Any] | Iterable[Any]) -> None:
    ensure_directory(path.parent)
    path.write_text(serialise_json(payload), encoding="utf-8")

