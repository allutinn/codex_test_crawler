from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Mapping

from playwright.async_api import Browser, BrowserContext, Page, async_playwright

from .config import CrawlConfig
from . import utils


class BrowserSession:
    """Manage a single Playwright browser session with consent handling."""

    def __init__(self, config: CrawlConfig) -> None:
        self._config = config
        self._playwright = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None
        self._consent_accepted = False

    async def __aenter__(self) -> "BrowserSession":
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(headless=self._config.headless)
        self._context = await self._browser.new_context(
            user_agent=self._config.user_agent,
            ignore_https_errors=True,
        )
        self._context.set_default_timeout(self._config.navigation_timeout_ms)
        self._page = await self._context.new_page()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:  # type: ignore[override]
        try:
            if self._page:
                await self._page.close()
            if self._context:
                await self._context.close()
            if self._browser:
                await self._browser.close()
        finally:
            if self._playwright:
                await self._playwright.stop()

    @property
    def page(self) -> Page:
        if not self._page:
            raise RuntimeError("BrowserSession is not initialised")
        return self._page

    async def goto(self, url: str, wait_for_idle: bool = True) -> Mapping[str, Any]:
        await self.page.goto(url, wait_until="domcontentloaded")
        if not self._consent_accepted:
            await self._accept_cookies()
        if wait_for_idle:
            try:
                await self.page.wait_for_load_state("networkidle")
            except Exception:
                pass
        await utils.random_delay(self._config.min_delay_seconds, self._config.max_delay_seconds)
        return await utils.extract_next_data(self.page)

    async def _accept_cookies(self) -> None:
        assert self._page is not None
        for label in ("Hyväksyn", "Salli kaikki", "Hyväksy kaikki"):
            button = self._page.locator(f"button:has-text(\"{label}\")")
            try:
                if await button.count() > 0:
                    await button.first.click()
                    await asyncio.sleep(1.0)
                    self._consent_accepted = True
                    return
            except Exception:
                continue
        self._consent_accepted = True

    @asynccontextmanager
    async def preserved_page(self) -> AsyncIterator[Page]:
        """Context manager yielding the underlying page and enforcing throttling."""

        if not self._page:
            raise RuntimeError("BrowserSession is not initialised")
        try:
            yield self._page
        finally:
            await utils.random_delay(self._config.min_delay_seconds, self._config.max_delay_seconds)

