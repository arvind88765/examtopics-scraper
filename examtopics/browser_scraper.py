import os
import sys
import time
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

from tqdm import tqdm

from .cleaner import clean_examtopics_html
from .http_client import SHARED_COORDINATOR, RateLimitError, ScanIncomplete
from .matching import (
    dedupe,
    discussion_entry_url,
    matches_discussion_entry,
    normalize_provider,
    provider_discussion_url,
    slug_from_url,
)
from .parsers import extract_discussion_entries, parse_discussion_page_count, raise_if_blocked
from .settings import (
    BLOCKED_URL_PARTS,
    DEFAULT_DELAY_RANGE,
    DEFAULT_RETRIES,
    DEFAULT_TIMEOUT_MS,
    POPUP_SUPPRESS_SCRIPT,
)

try:
    from camoufox.sync_api import Camoufox
    from camoufox.pkgman import LAUNCH_FILE, OS_NAME, launch_path
    from playwright.sync_api import Error as PlaywrightError
    from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
except ImportError:  # pragma: no cover
    Camoufox = None
    LAUNCH_FILE = {}
    OS_NAME = ""
    launch_path = None
    PlaywrightError = Exception
    PlaywrightTimeoutError = TimeoutError


class CamoufoxScraper:
    def __init__(
        self,
        provider: str = "",
        *,
        headless: bool = True,
        timeout_ms: int = DEFAULT_TIMEOUT_MS,
        retries: int = DEFAULT_RETRIES,
        delay_range: Tuple[float, float] = DEFAULT_DELAY_RANGE,
        coordinator=None,
    ):
        self.provider = normalize_provider(provider)
        self.base_url = provider_discussion_url(self.provider) if self.provider else ""
        self.headless = headless
        self.timeout_ms = timeout_ms
        self.retries = retries
        self.delay_range = delay_range
        self.coordinator = coordinator or SHARED_COORDINATOR
        self._attempt = 1
        self._manager = None
        self.browser = None
        self.context = None
        self.page = None

    def __enter__(self):
        if Camoufox is None:
            raise RuntimeError(
                "Camoufox missing. Run: pip install camoufox playwright beautifulsoup4 tqdm"
            )

        self._manager = Camoufox(
            headless=self.headless,
            humanize=True,
            locale="en-US",
            enable_cache=True,
            window=(1366, 900),
            executable_path=resolve_camoufox_executable(),
        )
        self.browser = self._manager.__enter__()
        self.context = self.browser.new_context(
            locale="en-US",
            viewport={"width": 1366, "height": 900},
        )
        self.context.add_init_script(POPUP_SUPPRESS_SCRIPT)
        self.page = self.context.new_page()
        self.page.set_default_timeout(self.timeout_ms)
        self.page.route("**/*", self._route_request)
        self.page.on("response", self._observe_response)
        return self

    def __exit__(self, exc_type, exc, tb):
        if self.context:
            self.context.close()
        if self._manager:
            self._manager.__exit__(exc_type, exc, tb)

    def fetch_html(self, url: str, *, wait_selector: Optional[str] = None) -> str:
        last_error = None
        for attempt in range(1, self.retries + 1):
            self._attempt = attempt
            # Cooldowns must finish outside Playwright's navigation timeout.
            self.coordinator.wait(url, attempt)
            try:
                response = self.page.goto(url, wait_until="domcontentloaded", timeout=self.timeout_ms)
                status = response.status if response is not None else None
                if status == 429:
                    self.coordinator.rate_limited(response.url, attempt, response.headers.get("retry-after"))
                    if attempt == self.retries:
                        raise RateLimitError(f"HTTP 429 exhausted {self.retries} attempts: {url}")
                    continue
                if status and status >= 500:
                    raise RuntimeError(f"HTTP {status}")

                if wait_selector:
                    try:
                        self.page.wait_for_selector(wait_selector, timeout=12_000)
                    except PlaywrightTimeoutError:
                        pass

                try:
                    self.page.wait_for_load_state("networkidle", timeout=8_000)
                except PlaywrightTimeoutError:
                    pass

                self._remove_popup()
                html = self.page.content()
                raise_if_blocked(html)
                return html
            except RateLimitError:
                raise
            except (PlaywrightError, RuntimeError, TimeoutError) as exc:
                last_error = exc
                if attempt < self.retries:
                    time.sleep(1.5 * attempt)

        raise RuntimeError(f"Failed to load {url}: {last_error}")

    def get_num_pages(self) -> int:
        html = self.fetch_html(self.base_url, wait_selector=".discussion-list-page-indicator")
        return parse_discussion_page_count(html)

    def fetch_page_links(self, page_number: int, search_string: str) -> List[str]:
        html = self.fetch_html(provider_discussion_url(self.provider, page_number), wait_selector="a.discussion-link")
        links = []

        for text, href in extract_discussion_entries(html):
            if matches_discussion_entry(text, href, search_string):
                links.append(discussion_entry_url(text, href))

        return dedupe(links)

    def get_discussion_links(self, page_numbers: Sequence[int], search_string: str) -> List[str]:
        links = []
        pages = list(page_numbers)
        completed = failed = 0
        for page_number in tqdm(pages, desc="Fetching Links", unit="page"):
            try:
                links.extend(self.fetch_page_links(page_number, search_string))
                completed += 1
            except RateLimitError as exc:
                exc.links = dedupe(links)
                exc.completed = completed
                exc.failed = failed + 1
                exc.not_attempted = len(pages) - completed - failed - 1
                raise
            except Exception as exc:
                failed += 1
                print(f"\nError on page {page_number}: {exc}")
        if failed:
            raise ScanIncomplete("Some browser listing pages failed", links=dedupe(links),
                                 completed=completed, failed=failed, not_attempted=0)
        return dedupe(links)

    def save_clean_discussion_page(self, url: str, output_dir: Path) -> Path:
        html = self.fetch_html(url, wait_selector="body")
        clean_html = clean_examtopics_html(html, url)
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"{slug_from_url(url)}.html"
        output_path.write_text(clean_html, encoding="utf-8")
        return output_path

    def _route_request(self, route):
        url = route.request.url.lower()
        if any(part in url for part in BLOCKED_URL_PARTS):
            route.abort()
            return
        route.continue_()

    def _observe_response(self, response):
        """Record resource cooldowns without blocking or raising through callbacks."""
        try:
            if response.status != 429:
                return
            if (response.request.is_navigation_request()
                    and response.frame == self.page.main_frame):
                # goto handles the final top-level response, including redirects.
                return
            self.coordinator.rate_limited(
                response.url, self._attempt, response.headers.get("retry-after"),
            )
        except Exception as exc:
            print(f"Could not observe browser resource rate limit: {exc}")

    def _remove_popup(self):
        self.page.evaluate(
            """
            () => {
              window.createPopup = () => {};
              for (const el of document.querySelectorAll("#notRemoverPopup, .popup-overlay")) {
                el.remove();
              }
              if (!document.getElementById("codex-popup-cleaner")) {
                const style = document.createElement("style");
                style.id = "codex-popup-cleaner";
                style.textContent = "#notRemoverPopup,.popup-overlay{display:none!important;visibility:hidden!important;pointer-events:none!important}";
                document.documentElement.appendChild(style);
              }
            }
            """
        )


def resolve_camoufox_executable() -> Optional[str]:
    if launch_path is None:
        return None

    raw_path = Path(launch_path())
    if sys.platform == "win32":
        package_id = Path(sys.executable).parent.name
        local_app_data = os.environ.get("LOCALAPPDATA")
        if package_id.startswith("PythonSoftwareFoundation.") and local_app_data:
            store_cache_path = (
                Path(local_app_data)
                / "Packages"
                / package_id
                / "LocalCache"
                / "Local"
                / "camoufox"
                / "camoufox"
                / "Cache"
                / LAUNCH_FILE.get(OS_NAME, "camoufox.exe")
            )
            if store_cache_path.exists():
                return str(store_cache_path)

    return str(raw_path)

