# `app/scraper_service.py` — Technical Documentation

---

## 1. Module Overview

`scraper_service.py` is the **service layer** responsible for orchestrating IMDB review scraping within the application. It acts as the bridge between higher-level application logic (e.g., a FastAPI route handler) and the lower-level scraping backend.

### Purpose

The module provides a clean, stable interface for two operations: parsing an IMDB URL into a canonical movie ID, and fetching reviews for that movie. As of this revision, scraping is performed via **Playwright (headless Chromium)** through the `app.imdb_playwright` module, replacing the previous Scrapy-based subprocess approach.

### Responsibilities

| Responsibility | Function |
|---|---|
| Parse and validate an IMDB URL to extract a canonical movie ID | `extract_movie_id` |
| Delegate review scraping to the Playwright backend | `scrape_imdb_reviews` |

### Position in the System

```
FastAPI Route Handler
       │
       ▼
scraper_service.py            ← YOU ARE HERE
  ├── extract_movie_id()      (URL parsing utility)
  └── scrape_imdb_reviews()   (scraping coordinator)
             │
             ▼
  app/imdb_playwright.py
  scrape_imdb_reviews_playwright()
  (Playwright + headless Chromium)
             │
             ▼
        IMDB Website
             │
             ▼
      list[dict] of reviews
```

---

## 2. Key Components

### 2.1 `extract_movie_id`

```python
def extract_movie_id(imdb_url: str) -> str:
```

#### Description

Parses an IMDB URL (or any string) and extracts the **IMDB title ID** — a token matching the pattern `tt` followed by one or more digits (e.g., `tt1375666`).

The function uses a regular expression search rather than strict URL parsing, so it tolerates a variety of input formats (full URLs, path-only strings, bare IDs) as long as the `tt\d+` pattern appears somewhere in the input.

#### Parameters

| Parameter | Type | Description |
|---|---|---|
| `imdb_url` | `str` | Any string expected to contain an IMDB title ID in the format `tt<digits>`. Typically a full IMDB URL such as `https://www.imdb.com/title/tt1375666/`. |

#### Return Value

| Type | Description |
|---|---|
| `str` | The matched IMDB title ID, e.g. `"tt1375666"`. |

#### Raises

| Exception | Condition |
|---|---|
| `ValueError` | Raised when the input string does not contain a pattern matching `tt\d+`. The error message includes the original input for diagnostics. |

#### Side Effects / Dependencies

- No I/O, no network access.
- Depends only on the standard library `re` module.
- Pure function; safe to call from any context including async code.

#### Example

```python
extract_movie_id("https://www.imdb.com/title/tt1375666/reviews")
# Returns: "tt1375666"

extract_movie_id("not-a-valid-url")
# Raises: ValueError("Invalid IMDB URL: could not find a title ID (tt...) in 'not-a-valid-url'")
```

---

### 2.2 `scrape_imdb_reviews`

```python
def scrape_imdb_reviews(
    movie_id: str,
    max_reviews: int = 75,
) -> list[dict]:
```

#### Description

The primary entry point for scraping IMDB reviews. This function delegates directly to `scrape_imdb_reviews_playwright` from `app.imdb_playwright`, which drives a headless Chromium browser via Playwright to fetch and parse review data from IMDB.

The import of `app.imdb_playwright` is performed **lazily** (inside the function body) rather than at module load time, which keeps the module importable even in environments where Playwright is not installed.

#### Parameters

| Parameter | Type | Default | Description |
|---|---|---|---|
| `movie_id` | `str` | *(required)* | A valid IMDB title ID (e.g., `"tt1375666"`). Typically obtained via `extract_movie_id()`. |
| `max_reviews` | `int` | `75` | The maximum number of reviews to scrape. Passed directly to the Playwright backend. |

#### Return Value

| Type | Description |
|---|---|
| `list[dict]` | A list of review dictionaries. Each dict contains the following keys (as defined by the scraping backend): `movie_id`, `movie_title`, `review_text`, `rating`, `review_date`, `source`. |

#### Raises

Exceptions are not explicitly caught here; any exceptions raised by `scrape_imdb_reviews_playwright` propagate directly to the caller. Refer to `app/imdb_playwright.py` for the specific failure modes of the Playwright backend.

#### Side Effects / Dependencies

- **Performs network I/O** by connecting to `www.imdb.com` via the Playwright backend.
- **Lazily imports** `app.imdb_playwright` at call time, not at module load time.
- Blocking and synchronous from the caller's perspective. Should be wrapped in `asyncio.run_in_executor` or a thread pool if invoked from an `async` FastAPI route.

#### Example

```python
movie_id = extract_movie_id("https://www.imdb.com/title/tt1375666/")
reviews = scrape_imdb_reviews(movie_id, max_reviews=50)
# Returns: [{"movie_id": "tt1375666", "movie_title": "Inception", "review_text": "...", ...}, ...]
```

---

## 3. What Changed

### Summary

This commit replaces the **Scrapy-based subprocess scraping architecture** with a **Playwright-based scraping backend**. The public API of both functions is unchanged, but the internal implementation of `scrape_imdb_reviews` has been completely rewritten.

### What Was Removed

The previous implementation of `scrape_imdb_reviews` contained substantial logic that no longer exists:

- **Subprocess orchestration**: The function previously built a self-contained Python script as an f-string and executed it via `subprocess.run([sys.executable, "-c", script], ...)`. This entire mechanism has been removed.
- **Temporary file I/O**: A `tempfile.TemporaryDirectory` was used as a data handoff channel. The subprocess wrote scraped results to `reviews.json`; the parent process then read and deserialized that file. This is entirely gone.
- **Inline Scrapy configuration**: The dynamically generated script embedded a full set of Scrapy settings (`FEEDS`, `AUTOTHROTTLE_ENABLED`, `AUTOTHROTTLE_TARGET_CONCURRENCY`, `DOWNLOAD_DELAY`, `USER_AGENT`, `HTTPERROR_ALLOWED_CODES`, `LOG_LEVEL`, `REQUEST_FINGERPRINTER_IMPLEMENTATION`). These settings no longer exist in this module.
- **Explicit error handling for known failure modes**: The previous code inspected the subprocess return code and stderr, raising a specific `RuntimeError` with a rate-limiting message when `"403"` appeared in stderr, and a generic `RuntimeError` for other non-zero exit codes.
- **120-second subprocess timeout**: `subprocess.run(..., timeout=120)` enforced a hard upper bound on scraping time. This constraint no longer exists at this layer (whether the Playwright backend enforces its own timeout is determined by `app/imdb_playwright.py`).
- **Standard library imports removed**: `json`, `os`, `subprocess`, `sys`, and `tempfile` are no longer imported, since none of their functionality is needed.

The module docstring was also simplified, removing the rationale about Twisted reactor isolation (which was specific to the Scrapy architecture).

The `extract_movie_id` docstring was condensed from a multi-line format to a single-line summary. The function logic itself is **unchanged**.

### What Was Added

- **Playwright delegation**: `scrape_imdb_reviews` now contains a single lazy import and a single `return` statement, delegating entirely to `scrape_imdb_reviews_playwright(movie_id, max_reviews)` from `app.imdb_playwright`.

### Why the Change Matters Functionally

| Concern | Previous Behavior | New Behavior |
|---|---|---|
| **Scraping mechanism** | Scrapy spider via isolated subprocess | Playwright headless Chromium, called directly |
| **Process model** | Spawns a child process per scrape call | Runs in the same process as the caller |
| **Twisted reactor isolation** | Subprocess prevents reactor/asyncio conflicts | No longer relevant; Playwright uses asyncio natively |
| **Timeout enforcement** | Hard 120-second limit at this layer | No explicit timeout at this layer |
| **403 error handling** | Dedicated `RuntimeError` with rate-limit message | Delegated to Playwright backend |
| **Temporary file usage** | Writes/reads `reviews.json` in a temp dir | No filesystem I/O at this layer |
| **Empty result handling** | Explicit `return []` on missing/empty output file | Delegated to Playwright backend |
| **Standard library footprint** | `json`, `os`, `re`, `subprocess`, `sys`, `tempfile` | `re` only |
| **Internal dependency** | `app.imdb_scraper.IMDBReviewSpider` (in subprocess) | `app.imdb_playwright.scrape_imdb_reviews_playwright` (lazy import) |

The architectural motivation also shifts: the previous design existed specifically to work around **Scrapy's Twisted reactor** being incompatible with FastAPI's asyncio event loop. Playwright does not carry this constraint, so subprocess isolation is no longer necessary.

Callers of `scrape_imdb_reviews` will observe the same return schema (`movie_id`, `movie_title`, `review_text`, `rating`, `review_date`, `source`) and the same default `max_reviews=75`, but the **source of data and failure modes** are now entirely determined by the Playwright backend rather than Scrapy.

---

## 4. Dependencies & Integration

### Standard Library Imports

| Module | Usage |
|---|---|
| `re` | Regular expression matching for IMDB title ID extraction in `extract_movie_id` |

### Internal Dependencies

| Module | Symbol | How It's Used |
|---|---|---|
| `app/imdb_playwright.py` | `scrape_imdb_reviews_playwright` | Imported lazily inside `scrape_imdb_reviews` at call time; performs the actual Playwright-based scraping |

> **Note:** The import of `scrape_imdb_reviews_playwright` occurs inside the function body, not at module load time. This means `scraper_service.py` has **no import-time dependency** on `app/imdb_playwright.py`, keeping the module importable in environments where Playwright may not be installed.

### Third-Party Dependencies

This module itself has no direct third-party imports. All third-party dependencies (Playwright, etc.) are encapsulated within `app/imdb_playwright.py`.

### What Depends on This Module

This module is intended to be consumed by:

- **FastAPI route handlers** (e.g., in `app/main.py` or a reviews router) that accept an IMDB URL from a client, call `extract_movie_id()` to validate and parse it, then call `scrape_imdb_reviews()` to fetch review data.
- **CLI scripts or background task runners** that need to trigger a scrape outside of the HTTP request lifecycle.

### Integration Contract

Callers should expect:

1. `extract_movie_id` to be called first for URL validation before invoking `scrape_imdb_reviews`.
2. `scrape_imdb_reviews` to be a **blocking, synchronous call** — it should be wrapped in `asyncio.run_in_executor` or a thread pool if called from an `async` FastAPI route to avoid blocking the event loop.
3. The returned list items to conform to the schema: `{movie_id, movie_title, review_text, rating, review_date, source}`.
4. Exception handling for scraping failures to be governed by the contract of `app/imdb_playwright.py`, since `scraper_service.py` no longer performs its own error interception.

---

`FUNCTIONAL_CHANGE: YES`
