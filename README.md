# ExamTopics Scraper

> Built on top of [swarnava-dutta/Free-Exam-Dumps](https://github.com/swarnava-dutta/Free-Exam-Dumps). The original repo collects discussion links. This version goes further and fetches every question page, extracts the full content, and saves it in a format you can actually study from.

---

## What this does differently

| Feature | Original | This Repo |
|---|---|---|
| Scrape discussion links | ✅ | ✅ |
| Fetch question content | ❌ | ✅ |
| Extract options A/B/C/D | ❌ | ✅ |
| Community answer (most voted) | ❌ | ✅ |
| Discussion comments | ❌ | ✅ |
| Output as `.txt` | ❌ | ✅ |
| Output as `.json` | ❌ | ✅ |
| JS popup bypassed | ❌ | ✅ |
| Questions sorted in order | ❌ | ✅ |

---

## How it works

ExamTopics shows a JS popup after a few page views that locks the content and kicks you back to page 1. Since this scraper fetches pages over raw HTTP without running JavaScript, that popup never triggers and the HTML comes back clean.

It scans discussion listing pages with one worker by default, filters the ones matching your exam code, then fetches each question page one by one. Vote counts are hidden behind a login wall, so the scraper reads all discussion comments and counts `Selected Answer: X` mentions to figure out the most accepted answer. Everything gets saved sorted by question number.

---

## Setup

**Requirements:** Python 3.9 or above

Clone the repo:

```bash
git clone https://github.com/arvind88765/examtopics-scraper.git
cd examtopics-scraper
```

Run setup (one time only):

```
install_dependencies.bat
```

This creates a local `.venv` folder, installs all required packages, and downloads the Camoufox browser runtime used as a fallback when the fast HTTP scanner gets blocked.

---

## Running

Double-click `run_scraper.bat`

It will ask you two things:

**Provider** - the vendor name as it appears on ExamTopics. Examples: `amazon`, `microsoft`, `servicenow`, `fortinet`, `cisco`

**Exam code** - the exam slug. Examples: `CIS-CSM`, `AIF-C01`, `FCP-FAZ-AN-7-6`, `DOP-C02`

After that it runs on its own. No more input needed.

### Pacing and rate limits

Normal runs are deliberately slower: uncached HTTP requests to the same host are spaced
3–6 seconds apart, including question downloads and retries. Increasing listing
workers does not bypass the shared host pacing. Cache hits return immediately.

HTTP 429 triggers a shared cooldown across HTTP/browser fetchers. Local backoff
starts at 30 seconds and doubles to a 120-second cap, plus small positive jitter.
A valid `Retry-After` seconds value or HTTP date can require a longer wait and is
never shortened to that cap. Defaults are configurable in `examtopics/settings.py`.
There are still three attempts; persistent 429 stops the phase, without switching
to a browser to evade the limit. The final response also sets a host cooldown.

Browser fallback paces explicit top-level page navigations before `goto`, outside
the navigation timeout. Assets, iframe requests and automatic redirect hops are
not individually paced. Subresource 429 responses update the responding host's
shared cooldown without blocking event callbacks; subsequent explicit navigations
to that host wait for it. A final navigation 429, including after redirects, uses
the same retry/exhaustion policy. Already-running asset requests are not recalled.

### Partial runs

The console reports completed, failed and not-attempted pages/questions. A failed
initial page-count request leaves the remaining page count unknown, not zero.
An incomplete scan saves collected links as `EXAM dumps.partial.txt` and does not
start question downloads or claim there were no matches. A failed question phase
saves successful questions as `EXAM partial questions.txt` and `.json`, and keeps
the discovered links in `EXAM dumps.partial.txt`. Empty partial results never
replace existing outputs; partial filenames do not replace complete filenames.
Partial files describe this run, not a merged checkpoint across runs.

---

## Output

Files are saved in the same folder as `run_scraper.bat`:

```
CIS-CSM questions.txt
CIS-CSM questions.json
```

The `.txt` is readable as a study document. The `.json` is structured data you can feed into other tools.

Sample from the txt:

```
════════════════════════════════════════════════════════════
QUESTION #1
════════════════════════════════════════════════════════════

Question:
Agents and managers cannot create knowledge articles from Community questions.

Options:
  A. True
  B. False

Community Votes:
  A -> 4
  B -> 5

Most Accepted Answer:
  B. False

Discussion:
  1. Selected Answer: A - requires knowledge harvester role, not agents
  2. Selected Answer: B - sn_customerservice_agent allows article creation

URL: https://www.examtopics.com/discussions/servicenow/view/91460-...
```

---

## Practice with the JSON

Upload the `.json` file to [quiz-three-orcin.vercel.app](https://quiz-three-orcin.vercel.app/) to turn it into a proper practice test with MCQ mode, answer reveal, and mock exam flow.

---

## Notes

Only free public questions get scraped. Questions locked behind contributor access come back empty - that is ExamTopics paywall, not a bug.

Successful HTTP HTML is cached in `.examtopics_cache` for 6 hours, even when a later
request fails. Re-running within that TTL reuses cached pages, but scans again and
rebuilds outputs: this is cache reuse, **not exact checkpoint resume**. Expired or
uncached pages require network requests again. Browser fallback HTML is not stored
in this HTTP cache. Cooldowns are shared within the running process, not persisted
across restarts; respect server limits before restarting.

---

## Video Guide

https://github.com/user-attachments/assets/1556fafd-1d11-4389-bd8b-1f1b2ec0babc




## Project structure

```
run_scraper.bat
install_dependencies.bat
main.py
examtopics/
  fast_scanner.py       - bounded listing scan (one worker by default)
  browser_scraper.py    - Camoufox fallback for blocked pages
  question_parser.py    - parses question pages into structured data
  http_client.py        - HTTP with retry and connection pooling
  cache.py              - HTML cache
  parsers.py            - HTML parsing and block detection
  matching.py           - provider, slug and question number matching
  output.py             - writes .txt and .json
  cleaner.py            - strips popups and noise from HTML
  settings.py           - all config in one place
```

---

## Credits

Core scraper, Camoufox integration, HTTP client and caching by [swarnava-dutta](https://github.com/swarnava-dutta/Free-Exam-Dumps). This repo adds question parsing, answer extraction, popup suppression and structured output on top of that foundation.

---

If this saved you time before an exam, a star helps others find it too ⭐
