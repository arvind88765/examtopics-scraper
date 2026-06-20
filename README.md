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
| JS popup bypassed | ✅ | ✅ |
| Questions sorted in order | ❌ | ✅ |

---

## How it works

ExamTopics shows a JS popup after a few page views that locks the content and kicks you back to page 1. Since this scraper fetches pages over raw HTTP without running JavaScript, that popup never triggers and the HTML comes back clean.

It scans all discussion listing pages for your provider in parallel, filters the ones matching your exam code, then fetches each question page one by one. Vote counts are hidden behind a login wall, so the scraper reads all discussion comments and counts `Selected Answer: X` mentions to figure out the most accepted answer. Everything gets saved sorted by question number.

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

Cache is stored in `.examtopics_cache` for 6 hours. Re-running within that window skips re-fetching pages. Delete the folder to force a fresh scrape.

---

## Video Guide

https://github.com/user-attachments/assets/1556fafd-1d11-4389-bd8b-1f1b2ec0babc




## Project structure

```
run_scraper.bat
install_dependencies.bat
main.py
examtopics/
  fast_scanner.py       - parallel listing scan (64 workers)
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

Core scraper, Camoufox integration, HTTP client, caching, and popup suppression by [swarnava-dutta](https://github.com/swarnava-dutta/Free-Exam-Dumps). This repo adds question parsing, answer extraction, and structured output on top of that foundation.

---

If this saved you time before an exam, a star helps others find it too ⭐
