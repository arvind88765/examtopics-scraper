from pathlib import Path

from tqdm import tqdm

from examtopics.output import (
    write_grouped_links_to_file,
    write_questions_to_csv,
    write_questions_to_json,
    write_questions_to_txt,
)
from examtopics.browser_scraper import CamoufoxScraper
from examtopics.cache import HtmlCache
from examtopics.fast_scanner import FastDiscussionScanner
from examtopics.http_client import HttpFetcher
from examtopics.matching import build_page_numbers, display_slug, extract_topic_question, normalize_provider
from examtopics.output import (
    write_grouped_links_to_file,
    write_questions_to_json,
    write_questions_to_txt,
)
from examtopics.question_parser import parse_question_page
from examtopics.settings import (
    DEFAULT_CACHE_DIR,
    DEFAULT_CACHE_TTL_SECONDS,
    DEFAULT_DELAY_RANGE,
    DEFAULT_RETRIES,
    DEFAULT_REQUEST_WORKERS,
    DEFAULT_TIMEOUT_MS,
)


def main():
    print_header()

    while True:
        print("Choose option:")
        print("  1. Scrape links only")
        print("  2. Scrape + fetch questions (student-friendly output)")
        print("  3. Exit")
        print()

        choice = input("Enter choice [2]: ").strip() or "2"
        if choice == "1":
            scrape_links_only()
            return
        if choice == "2":
            scrape_with_questions()
            return
        if choice == "3":
            return

        print("Invalid choice.\n")


def print_header():
    print()
    print("=" * 60)
    print("  ExamTopics Scraper")
    print("=" * 60)
    print()


def scrape_links_only():
    provider, exam_code, cache = _get_common_inputs()
    links = scan_discussion_links(provider, exam_code, cache)
    filename = f"{display_slug(exam_code).upper()} dumps.txt"
    print(f"\nYour file will be named: {filename}")
    write_grouped_links_to_file(filename, links)
    print(f"File generation complete. {len(links)} links found.")


def scrape_with_questions():
    provider, exam_code, cache = _get_common_inputs()
    links = scan_discussion_links(provider, exam_code, cache)

    if not links:
        print("No links found.")
        return

    # Sort by topic number then question number
    links = sorted(links, key=lambda u: extract_topic_question(u))

    print(f"\nFound {len(links)} links. Fetching question pages...")

    fetcher = build_fetcher(cache)
    questions = []
    failed = 0

    with tqdm(total=len(links), desc="Fetching Questions", unit="q") as pbar:
        for url in links:
            try:
                html = fetcher.fetch_html(url)
                q = parse_question_page(html, url=url)
                questions.append(q)
            except Exception as exc:
                failed += 1
                tqdm.write(f"✗ {url} — {exc}")
            pbar.update(1)

    slug = display_slug(exam_code).upper()
    txt_file  = f"{slug} questions.txt"
    json_file = f"{slug} questions.json"

    write_questions_to_txt(txt_file, questions)
    write_questions_to_json(json_file, questions)

    print(f"\nDone! {len(questions)} questions saved.")
    print(f"  → {txt_file}")
    print(f"  → {json_file}")


def _get_common_inputs():
    provider  = prompt_required("Provider (e.g. amazon, microsoft, servicenow): ")
    exam_code = prompt_required("Exam code (e.g. AIF-C01, CSA, aws-devops-engineer): ")
    provider  = normalize_provider(provider)
    cache     = HtmlCache(Path(DEFAULT_CACHE_DIR), DEFAULT_CACHE_TTL_SECONDS)
    return provider, exam_code, cache


def prompt_required(prompt: str) -> str:
    while True:
        value = input(prompt).strip()
        if value:
            return value
        print("[ERROR] Value is required.\n")


def build_fetcher(cache: HtmlCache) -> HttpFetcher:
    return HttpFetcher(
        timeout=DEFAULT_TIMEOUT_MS // 1000,
        retries=DEFAULT_RETRIES,
        cache=cache,
        refresh_cache=False,
    )


def scan_discussion_links(provider: str, exam_code: str, cache: HtmlCache):
    try:
        scanner = FastDiscussionScanner(provider, build_fetcher(cache), delay_range=DEFAULT_DELAY_RANGE)
        total_pages = scanner.get_num_pages()
        page_numbers = build_page_numbers(total_pages, 1, None, None)
        print(f"\nScanning Pages: {page_numbers[0]}-{page_numbers[-1]} ({len(page_numbers)} pages)")
        return scanner.scan(page_numbers, exam_code, workers=DEFAULT_REQUEST_WORKERS)
    except Exception as exc:
        print(f"Fast scan failed; falling back to Camoufox: {exc}")

    with CamoufoxScraper(
        provider,
        headless=True,
        timeout_ms=DEFAULT_TIMEOUT_MS,
        retries=DEFAULT_RETRIES,
        delay_range=DEFAULT_DELAY_RANGE,
    ) as scraper:
        total_pages = scraper.get_num_pages()
        page_numbers = build_page_numbers(total_pages, 1, None, None)
        print(f"\nScanning Pages: {page_numbers[0]}-{page_numbers[-1]} ({len(page_numbers)} pages)")
        return scraper.get_discussion_links(page_numbers, exam_code)


if __name__ == "__main__":
    main()
