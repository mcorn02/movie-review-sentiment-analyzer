# `app/imdb_playwright.py` — Technical Documentation

---

## 1. Module Overview

### Purpose

`app/imdb_playwright.py` is a browser-automation scraping module responsible for extracting user review data from IMDb movie review pages. It uses Playwright's synchronous API to drive a real Chromium browser, enabling it to bypass JavaScript-rendered content and Web Application Firewall (WAF) bot-detection mechanisms that would defeat simpler HTTP-based scrapers.

### Responsibilities

- Launch a headless Chromium browser with anti-detection hardening.
- Navigate to an IMDb movie's user review page using a structured URL.
- Handle WAF challenges and dynamic page loading gracefully.
- Attempt to paginate through reviews by clicking "load more" controls.
- Extract structured review data (text, rating, date, movie title) from multiple possible DOM layouts (IMDb has both a legacy and a modern React-based UI).
- Return a normalized list of review dictionaries for downstream consumption.

### Where It Fits in the System

This module sits in the **data ingestion layer** of the application. It is the IMDb-specific scraping backend, likely called by a higher-level orchestration layer (e.g., an API route, a task runner, or a review aggregation service) that requests reviews for a given movie by its IMDb title ID. Its output feeds into whatever processing pipeline the application runs (sentiment analysis, storage, display, etc.).

---

## 2. Key Components

### Function: `scrape_imdb_reviews_playwright`

```python
def scrape_imdb_reviews_playwright(movie_id: str, max_reviews: int = 75) -> list[dict]:
```

#### What It Does

Orchestrates the full scraping workflow for IMDb user reviews of a single movie:

1. Constructs the target URL from the provided IMDb movie ID.
2. Launches a headless Chromium browser instance with bot-detection mitigations applied.
3. Creates a browser context spoofing a real macOS Chrome user agent with an `en-US` locale.
4. Injects a JavaScript snippet to mask the `navigator.webdriver` property, making the browser appear non-automated.
5. Navigates to the reviews page and waits for review content to appear, with a two-stage fallback wait to accommodate WAF-induced page reloads.
6. Cleans and extracts the movie title from the page's `<title>` tag.
7. Attempts up to **3 "load more" button clicks** to expand the number of visible reviews before scraping.
8. Queries the DOM using a prioritized set of CSS selectors to accommodate both IMDb's modern (`ipc-*`) and legacy (`lister-item-content`) UI layouts.
9. For each review container, extracts the review text, numeric rating (1–10), and review date.
10. Filters out containers with no text or fewer than 20 characters of review text.
11. Closes the browser and returns all collected reviews.

#### Parameters

| Parameter | Type | Default | Description |
|---|---|---|---|
| `movie_id` | `str` | *(required)* | The IMDb title identifier (e.g., `"tt0111161"` for *The Shawshank Redemption*). Used directly in URL construction: `https://www.imdb.com/title/{movie_id}/reviews/`. |
| `max_reviews` | `int` | `75` | The maximum number of reviews to return. Limits both the "load more" loop (exits early if already satisfied) and the container iteration slice (`containers[:max_reviews]`). |

#### Return Value

Returns a `list[dict]`. Each dictionary in the list represents one user review and contains the following keys:

| Key | Type | Description |
|---|---|---|
| `movie_id` | `str` | The IMDb title ID passed as input. |
| `movie_title` | `str` | The movie title, cleaned from the page `<title>` element. |
| `review_text` | `str` | The full visible text of the user's review. |
| `rating` | `int` \| `None` | The user's numeric rating (1–10), or `None` if not present or unparseable. |
| `review_date` | `str` \| `None` | The review date as a string (e.g., `"15 March 2023"`), or `None` if not found. |
| `source` | `str` | Always `"imdb"`. Identifies the data origin for downstream processing. |

Returns an **empty list** `[]` if no reviews could be extracted (e.g., total WAF block, no matching DOM elements).

#### Side Effects & Dependencies

- **Launches a subprocess**: Spawns a real Chromium browser process. This is a heavyweight operation with non-trivial memory and CPU cost per call.
- **Network I/O**: Makes live HTTP requests to `imdb.com`. Subject to network latency, rate limiting, and IMDb's evolving anti-bot measures.
- **Timing dependencies**: Uses `wait_for_timeout` (wall-clock sleeps) to accommodate WAF challenge resolution and "load more" animation. Total execution time can range from a few seconds to well over a minute depending on network conditions and WAF behavior.
- **No persistent state**: The browser and context are fully created and destroyed within each function call. No cookies, sessions, or cache are persisted between calls.
- **No error propagation**: Most internal exceptions are silently caught and swallowed. The function will return a partial or empty list rather than raising an exception in most failure scenarios.

#### Internal Selector Strategy

The function employs a **priority-ordered fallback** pattern at two levels:

**Container selection** (evaluated left-to-right; first non-empty result wins):
```
1. article.user-review-item          ← Modern IMDb UI
2. div[data-testid="review-card"]    ← Modern IMDb data-testid
3. div.lister-item-content           ← Legacy IMDb UI
4. article                           ← Generic fallback
```

**Review text selection** (per-container, first match wins):
```
1. div.ipc-html-content-inner-div    ← Modern IMDb UI
2. div.text.show-more__control       ← Modern collapsible text
3. div.content div.text              ← Legacy IMDb UI
```

**Rating selection** (single multi-selector query):
```
span.ipc-rating-star--rating,        ← Modern IMDb star rating
span.rating-other-user-rating span   ← Legacy IMDb rating
```

**Date selection** (single multi-selector query):
```
span.review-date,                    ← Span variant
li.review-date                       ← List-item variant
```

---

## 3. What Changed

This file is **newly introduced** in this commit (git status: `new file mode 100644`). There is no prior version to diff against; the entire module is a net-new addition.

### What Was Added

The complete `app/imdb_playwright.py` module was created with 101 lines of code, including:

- The `scrape_imdb_reviews_playwright` function in its entirety.
- The Playwright-based Chromium automation stack.
- Anti-detection mitigations (`--disable-blink-features=AutomationControlled`, `navigator.webdriver` masking, spoofed user agent).
- A two-stage WAF challenge wait strategy.
- A "load more" pagination loop (up to 3 clicks).
- Multi-selector DOM extraction logic covering both modern and legacy IMDb UIs.
- A minimum text length filter (< 20 characters discarded).
- A normalized output schema with the `source: "imdb"` tag.

### Why the Change Matters Functionally

Prior to this commit, the application had no Playwright-based IMDb scraping capability. This addition enables the system to:

- **Scrape JavaScript-rendered IMDb review pages** that cannot be accessed with simple `requests`/`httpx`-style HTTP clients.
- **Bypass common bot-detection measures** through browser fingerprint spoofing.
- **Handle IMDb's dual UI** (legacy and modern React-based) without requiring separate code paths.
- **Tolerate WAF interruptions** gracefully rather than failing hard.

### Behavioral Notes for New Code

- The function is **blocking and synchronous**. In an async web framework (e.g., FastAPI), it must be run in a thread pool executor to avoid blocking the event loop.
- Silent exception handling throughout means callers **cannot distinguish** between a network failure, a WAF block, and a movie with zero reviews — all return `[]`.
- The `max_reviews` guard in the "load more" loop checks `len(reviews)` **before** any reviews are collected (the list is always empty at that point in the current code), meaning the loop will always run all 3 iterations regardless of `max_reviews`. The effective limit is applied only during container iteration via `containers[:max_reviews]`.

---

## 4. Dependencies & Integration

### External Dependencies

| Dependency | Import | Purpose |
|---|---|---|
| `playwright` | `from playwright.sync_api import sync_playwright` | Browser automation. Requires the `playwright` Python package and the Chromium browser binary (installed via `playwright install chromium`). |

### System Dependencies

- **Chromium browser binary**: Must be installed separately via `playwright install chromium`. Not bundled with the Python package.
- **Network access to `imdb.com`**: The scraper makes live requests; firewall rules or IMDb IP blocks will cause silent failures.

### What This Module Exports

| Symbol | Type | Visibility |
|---|---|---|
| `scrape_imdb_reviews_playwright` | `function` | Public — the sole public interface of this module. |

### What Likely Depends on This Module

Based on its output schema and naming conventions, this module is expected to be imported by:

- **Review aggregation services** or **API route handlers** that collect reviews across multiple sources and merge them by `movie_id`.
- **Data pipeline tasks** (e.g., Celery workers, background jobs) that periodically refresh review data.
- **Sentiment analysis preprocessing** stages that consume the `review_text` field.

Example integration pattern:

```python
from app.imdb_playwright import scrape_imdb_reviews_playwright

reviews = scrape_imdb_reviews_playwright("tt0111161", max_reviews=50)
# reviews → [{'movie_id': 'tt0111161', 'movie_title': 'The Shawshank Redemption', ...}, ...]
```

### Integration Considerations

- **Thread safety**: Each call to `scrape_imdb_reviews_playwright` creates and destroys its own browser instance. Multiple concurrent calls will spawn multiple Chromium processes, which may exhaust system resources. A semaphore or task queue is recommended for production use.
- **No caching**: Results are not cached. Repeated calls with the same `movie_id` will make full browser round-trips each time.
- **No retry logic**: Beyond the two-stage WAF wait, there is no retry mechanism. Transient failures produce empty results silently.

---

`FUNCTIONAL_CHANGE: YES`
