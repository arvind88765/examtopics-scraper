import threading
import time
import math
import random
import re
from concurrent.futures import CancelledError
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urlsplit, urljoin
from typing import Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .cache import HtmlCache
from .parsers import raise_if_blocked
from .settings import (
    MAX_HTTP_POOL_SIZE, REQUEST_HEADERS, DEFAULT_DELAY_RANGE,
    DEFAULT_429_BACKOFF_SECONDS, MAX_429_BACKOFF_SECONDS, RATE_LIMIT_JITTER_RANGE,
)


class ScanIncomplete(RuntimeError):
    def __init__(self, message, *, links=(), completed=0, failed=1, not_attempted=None):
        super().__init__(message)
        self.links = list(links)
        self.completed = completed
        self.failed = failed
        self.not_attempted = not_attempted


class RateLimitError(ScanIncomplete):
    pass


def retry_after_seconds(value):
    """Reject malformed/non-finite values; never cap a valid server delay."""
    if not value:
        return 0.0
    value = str(value).strip()
    if re.fullmatch(r"[0-9]+(?:\.[0-9]+)?", value):
        seconds = float(value)
    else:
        try:
            date = parsedate_to_datetime(value)
            if date.tzinfo is None:
                date = date.replace(tzinfo=timezone.utc)
            seconds = (date - datetime.now(timezone.utc)).total_seconds()
        except (ValueError, TypeError, OverflowError):
            return 0.0
    return max(0.0, seconds) if math.isfinite(seconds) else 0.0


class RequestCoordinator:
    def __init__(self, delay_range=DEFAULT_DELAY_RANGE,
                 backoff=DEFAULT_429_BACKOFF_SECONDS, cap=MAX_429_BACKOFF_SECONDS):
        self.delay_range = delay_range
        self.backoff = backoff
        self.cap = cap
        self._lock = threading.Lock()
        self._ready = {}

    def wait(self, url, attempt, stop_event=None):
        host = urlsplit(url).netloc.lower()
        while True:
            with self._lock:
                if stop_event is not None and stop_event.is_set():
                    raise CancelledError("Scan stopped after rate-limit exhaustion")
                now = time.monotonic()
                delay = self._ready.get(host, 0) - now
                if delay <= 0:
                    self._ready[host] = now + random.uniform(*self.delay_range)
                    return
            print(f"Request {url} attempt {attempt}: waiting {delay:.1f}s")
            if stop_event is not None:
                stop_event.wait(min(delay, 60.0))
            else:
                time.sleep(min(delay, 60.0))

    def rate_limited(self, url, attempt, retry_after):
        delay = max(retry_after_seconds(retry_after),
                    min(self.cap, self.backoff * (2 ** (attempt - 1))))
        delay += random.uniform(*RATE_LIMIT_JITTER_RANGE)
        with self._lock:
            host = urlsplit(url).netloc.lower()
            self._ready[host] = max(self._ready.get(host, 0), time.monotonic() + delay)
        print(f"HTTP 429 {url} attempt {attempt}: host cooldown {delay:.1f}s")


SHARED_COORDINATOR = RequestCoordinator()


class SessionFactory:
    def __init__(self, pool_size: int = MAX_HTTP_POOL_SIZE):
        self.pool_size = pool_size
        self._thread_local = threading.local()

    def get(self) -> requests.Session:
        session = getattr(self._thread_local, "session", None)
        if session is not None:
            return session

        retry = Retry(
            total=0,
            connect=0,
            read=0,
            redirect=2,
            status=0,
            allowed_methods=frozenset(["GET"]),
        )
        adapter = HTTPAdapter(
            pool_connections=self.pool_size,
            pool_maxsize=self.pool_size,
            max_retries=retry,
        )
        session = requests.Session()
        session.headers.update(REQUEST_HEADERS)
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        self._thread_local.session = session
        return session


class HttpFetcher:
    def __init__(
        self,
        *,
        timeout: int,
        retries: int,
        cache: Optional[HtmlCache],
        refresh_cache: bool = False,
        session_factory: Optional[SessionFactory] = None,
        coordinator: Optional[RequestCoordinator] = None,
    ):
        self.timeout = timeout
        self.retries = retries
        self.cache = cache
        self.refresh_cache = refresh_cache
        self.session_factory = session_factory or SessionFactory()
        self.coordinator = coordinator or SHARED_COORDINATOR

    def fetch_html(self, url: str, *, stop_event=None, on_dispatch=None) -> str:
        if self.cache is not None and not self.refresh_cache:
            cached_html = self.cache.read(url)
            if cached_html is not None:
                return cached_html

        last_error = None
        for attempt in range(1, self.retries + 1):
            self.coordinator.wait(url, attempt, stop_event)
            try:
                request_url = url
                for redirect in range(11):
                    if redirect:
                        self.coordinator.wait(request_url, attempt, stop_event)
                    if on_dispatch is not None:
                        on_dispatch()
                    response = self.session_factory.get().get(
                        request_url, timeout=self.timeout, allow_redirects=False,
                    )
                    if response.status_code not in (301, 302, 303, 307, 308):
                        break
                    location = response.headers.get("Location")
                    if not location:
                        raise RuntimeError(f"Redirect without Location: {request_url}")
                    request_url = urljoin(request_url, location)
                    response.close()
                else:
                    raise RuntimeError(f"Too many redirects: {url}")
                if response.status_code == 429:
                    self.coordinator.rate_limited(request_url, attempt, response.headers.get("Retry-After"))
                    response.close()
                    if attempt == self.retries:
                        if stop_event is not None:
                            stop_event.set()
                        raise RateLimitError(f"HTTP 429 exhausted {self.retries} attempts: {url}")
                    continue
                response.raise_for_status()
                raise_if_blocked(response.text)
                if self.cache is not None:
                    self.cache.write(url, response.text)
                return response.text
            except (RateLimitError, CancelledError):
                raise
            except Exception as exc:
                last_error = exc
                if attempt < self.retries:
                    time.sleep(1.0 * attempt)

        raise RuntimeError(f"Failed to load {url}: {last_error}")

