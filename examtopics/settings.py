BASE_URL = "https://www.examtopics.com"

DEFAULT_TIMEOUT_MS = 45_000
DEFAULT_RETRIES = 3
DEFAULT_DELAY_RANGE = (3.0, 6.0)
MAX_HTTP_POOL_SIZE = 64
DEFAULT_REQUEST_WORKERS = MAX_HTTP_POOL_SIZE
DEFAULT_CLEAN_WORKERS = 4
DEFAULT_CACHE_DIR = ".examtopics_cache"
DEFAULT_CACHE_TTL_SECONDS = 6 * 60 * 60

REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Connection": "keep-alive",
}

POPUP_SUPPRESS_SCRIPT = """
(() => {
  const killExamTopicsPopup = () => {
    for (const el of document.querySelectorAll("#notRemoverPopup, .popup-overlay")) {
      el.remove();
    }
    if (document.body) {
      document.body.style.overflow = "";
      document.body.style.pointerEvents = "";
    }
    document.documentElement.style.overflow = "";
  };

  try {
    Object.defineProperty(window, "createPopup", {
      value: () => {},
      writable: false,
      configurable: true
    });
  } catch (_) {}

  window.addEventListener("DOMContentLoaded", killExamTopicsPopup, true);
  window.addEventListener("load", killExamTopicsPopup, true);
  window.setInterval(killExamTopicsPopup, 200);
})();
"""

BLOCKED_URL_PARTS = (
    "googletagmanager.com",
    "google-analytics.com",
    "doubleclick.net",
    "googlesyndication.com",
    "googleadservices.com",
    "facebook.net",
    "hotjar.com",
    "clarity.ms",
    "visualwebsiteoptimizer.com",
)
