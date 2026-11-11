import threading
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED, CancelledError
from typing import List, Sequence, Tuple

from tqdm import tqdm

from .http_client import HttpFetcher, RateLimitError, ScanIncomplete
from .matching import (
    dedupe,
    discussion_entry_url,
    matches_discussion_entry,
    normalize_provider,
    provider_discussion_url,
)
from .parsers import extract_discussion_entries, parse_discussion_page_count
from .settings import DEFAULT_DELAY_RANGE


class FastDiscussionScanner:
    def __init__(
        self,
        provider: str,
        fetcher: HttpFetcher,
        *,
        delay_range: Tuple[float, float] = DEFAULT_DELAY_RANGE,
    ):
        self.provider = normalize_provider(provider)
        self.fetcher = fetcher
        self.delay_range = delay_range
        self._stop = threading.Event()

    def get_num_pages(self) -> int:
        html = self.fetcher.fetch_html(provider_discussion_url(self.provider))
        return parse_discussion_page_count(html)

    def fetch_page_links(self, page_number: int, search_string: str, dispatched=None) -> List[str]:
        html = self.fetcher.fetch_html(
            provider_discussion_url(self.provider, page_number), stop_event=self._stop,
            on_dispatch=dispatched.set if dispatched is not None else None,
        )
        links = []

        for text, href in extract_discussion_entries(html):
            if matches_discussion_entry(text, href, search_string):
                links.append(discussion_entry_url(text, href))

        return dedupe(links)

    def scan(self, page_numbers: Sequence[int], search_string: str, workers: int) -> List[str]:
        links = []
        pages = list(page_numbers)
        remaining = iter(pages)
        self._stop.clear()
        completed = failed = 0
        fatal = None
        with ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
            futures = {}

            def schedule():
                page = next(remaining, None)
                if page is not None:
                    dispatched = threading.Event()
                    future = executor.submit(self.fetch_page_links, page, search_string, dispatched)
                    futures[future] = (page, dispatched)

            for _ in range(min(len(pages), max(1, workers))):
                schedule()
            with tqdm(total=len(pages), desc="Fetching Links", unit="page") as pbar:
                while futures:
                    done, _ = wait(futures, return_when=FIRST_COMPLETED)
                    for future in done:
                        page_number, dispatched = futures.pop(future)
                        try:
                            links.extend(future.result())
                            completed += 1
                        except CancelledError:
                            if dispatched.is_set():
                                failed += 1
                            continue
                        except RateLimitError as exc:
                            failed += 1
                            fatal = exc
                            self._stop.set()
                        except Exception as exc:
                            failed += 1
                            print(f"\nError on page {page_number}: {exc}")
                        pbar.update(1)
                    if self._stop.is_set():
                        for future in futures:
                            future.cancel()
                    else:
                        for _ in done:
                            schedule()

        if fatal is not None or failed:
            error = fatal or ScanIncomplete("Some listing pages failed")
            error.links = dedupe(links)
            error.completed = completed
            error.failed = failed
            error.not_attempted = len(pages) - completed - failed
            raise error

        return dedupe(links)

