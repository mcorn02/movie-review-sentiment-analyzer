# `app/scraper_service.py` — Technical Documentation

---

## 1. Module Overview

`scraper_service.py` is the **service layer** responsible for orchestrating IMDB review scraping within the application. It acts as the bridge between higher-level application logic (e.g., a FastAPI route handler) and the lower-level scraping backend.

### Purpose

The module provides a clean, stable interface for two operations: parsing an IMDB URL into a canonical movie ID, and fetching reviews for that movie. Scraping is performed via **Playwright (headless Chromium)** through the `app.imdb_playwright` module.

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
    max_reviews: int = 100,
) -> list[dict]:
```

#### Description

The primary entry point for scraping IMDB reviews. This function delegates directly to `scrape_imdb_reviews_playwright` from `app.imdb_playwright`, which drives a headless Chromium browser via Playwright to fetch and parse review data from IMDB.

The import of `app.imdb_playwright` is performed **lazily** (inside the function body) rather than at module load time, which keeps the module importable even in environments where Playwright is not installed.

#### Parameters

| Parameter | Type | Default | Description |
|---|---|---|---|
| `movie_id` | `str` | *(required)* | A valid IMDB title ID (e.g., `"tt1375666"`). Typically obtained via `extract_movie_id()`. |
| `max_reviews` | `int` | `100` | The maximum number of reviews to scrape. Passed directly to the Playwright backend. |

#### Return Value

| Type | Description |
|---|---|
| `list[dict]` | A list of review dictionaries. Each dict contains the following keys (as defined by the scraping backend): `movie_id`, `movie_title`, `review_text`, `rating`, `review_date`, `source`. |

#### Review Dict Schema

| Key | Type | Description |
|---|---|---|
| `movie_id` | `str` | The IMDB title ID (e.g., `"tt1375666"`). |
| `movie_title` | `str` | The title of the movie as reported by IMDB. |
| `review_text` | `str` | The full text body of the review. |
| `rating` | `str` or `None` | The numeric rating given by the reviewer, if present. |
| `review_date` | `str` | The date the review was posted. |
| `source` | `str` | The origin of the review (e.g., `"imdb"`). |

#### Raises

Exceptions are not explicitly caught here; any exceptions raised by `scrape_imdb_reviews_playwright` propagate directly to the caller. Refer to `app/imdb_playwright.py` for the specific failure modes of the Playwright backend.

#### Side Effects / Dependencies

- **Performs network I/O** by connecting to `www.imdb.com` via the Playwright backend.
- **Lazily imports** `app.imdb_playwright` at call time, not at module load time.
- Blocking and synchronous from the caller's perspective. Should be wrapped in `asyncio.run_in_executor` or a thread pool if invoked from an `async` FastAPI route to avoid blocking the event loop.

#### Example

```python
movie_id = extract_movie_id("https://www.imdb.com/title/tt1375666/")
reviews = scrape_imdb_reviews(movie_id, max_reviews=50)
# Returns:
# [
#   {
#     "movie_id": "tt1375666",
#     "movie_title": "Inception",
#     "review_text": "A mind-bending thriller...",
#     "rating": "9",
#     "review_date": "2010-07-20",
#     "source": "imdb"
#   },
#   ...
# ]
```

---

## 3. What Changed

### Summary

This commit increases the **default value of `max_reviews`** in `scrape_imdb_reviews` from `75` to `100`. This is a targeted, single-line change to a parameter default; no logic, structure, or other behavior was modified.

### Diff Detail

```diff
-    max_reviews: int = 75,
+    max_reviews: int = 100,
```

### What Was Modified

| Element | Previous Value | New Value |
|---|---|---|
| `scrape_imdb_reviews` — `max_reviews` default | `75` | `100` |

### Why the Change Matters Functionally

Any caller that invokes `scrape_imdb_reviews` **without explicitly passing `max_reviews`** will now request up to **100 reviews** per scrape instead of 75. This is a user-visible behavioral change in the following sense:

- **More data returned by default**: Scrapes that previously returned at most 75 reviews will now return up to 100, assuming the movie has sufficient reviews on IMDB.
- **Longer scrape times by default**: Since the Playwright backend must load and parse more content, unparameterized calls will take longer to complete.
- **Increased network activity**: Additional page interactions or scroll events may be required in the Playwright backend to retrieve the extra 25 reviews.

Callers that **explicitly pass `max_reviews`** are entirely unaffected by this change.

### Behavioral Differences from Before

| Scenario | Previous Behavior | New Behavior |
|---|---|---|
| `scrape_imdb_reviews("tt1375666")` | Scrapes up to 75 reviews | Scrapes up to 100 reviews |
| `scrape_imdb_reviews("tt1375666", max_reviews=50)` | Scrapes up to 50 reviews | Scrapes up to 50 reviews *(unchanged)* |
| `scrape_imdb_reviews("tt1375666", max_reviews=100)` | Scrapes up to 100 reviews | Scrapes up to 100 reviews *(unchanged)* |

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
4. Exception handling for scraping failures to be governed by the contract of `app/imdb_playwright.py`, since `scraper_service.py` does not perform its own error interception.
5. **The default scrape size is now 100 reviews.** Callers relying on the previous default of 75 that wish to preserve the old behavior must now pass `max_reviews=75` explicitly.

---

`FUNCTIONAL_CHANGE: YES`
