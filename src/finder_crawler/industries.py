from __future__ import annotations

from typing import Dict, List

from .browser import BrowserSession


async def fetch_industries(session: BrowserSession) -> Dict[str, List[str]]:
    """Return mapping of alphabet letter to industry names."""

    data = await session.goto("https://www.finder.fi/toimialat")
    categories = data["props"]["pageProps"]["categories"]
    return {letter: [entry["name"] for entry in entries] for letter, entries in categories.items()}


async def iter_industry_names(session: BrowserSession) -> List[str]:
    industries = await fetch_industries(session)
    ordered_letters = sorted(industries.keys())
    names: List[str] = []
    for letter in ordered_letters:
        names.extend(industries[letter])
    return names

