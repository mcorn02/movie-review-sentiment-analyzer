# `app/imdb_playwright.py` — Technical Documentation

---

## 1. Module Overview

### Purpose

`app/imdb_playwright.py` is a browser-automation scraping module responsible for extracting user review data from IMDb movie review pages. It uses Playwright's synchronous API to drive a real Chromium browser, enabling it to bypass JavaScript-rendered content and Web Application Firewall (WAF) bot-detection mechanisms that would defeat simpler HTTP-based scrapers.

### Responsibilities

- Launch a headless Chromium browser with anti-detection hardening.
- Navigate to an IMDb movie's user review page using a structured URL.
- Handle WAF challenges and dynamic page loading gracefully.
- Paginate through reviews by repeatedly clicking "load more" controls, scaling up to approximately 500 reviews per call.
- Extract structured review data (text, rating, date, movie title) from the modern IMDb React-based DOM layout.
- Return a normalized list of review dictionaries for downstream consumption.

### Where It Fits in the System

This module sits in the **data ingestion layer** of the application. It is the IMDb-specific scraping backend, likely called by a higher-level orchestration layer (e.g., an API route, a task runner, or a review aggregation service) that requests reviews for a given movie by its IMDb title ID. Its output feeds into whatever processing pipeline the application runs (sentiment analysis, storage, display, etc.).

---

## 2. Key Components

### Function: `scrape_imdb_reviews_playwright`

```python
def scrape_imdb_reviews_playwright(movie_id: str, max_reviews: int = 100) -> list[dict]:
```

#### What It Does

Orchestrates the full scraping workflow for IMDb user reviews of a single movie:

1. Constructs the target URL from the provided IMDb movie ID.
2. Launches a headless Chromium browser instance with bot-detection mitigations applied.
3. Creates a browser context spoofing a real macOS Chrome user agent with an `en-US` locale.
4. Injects a JavaScript snippet to mask the `navigator.webdriver` property, making the browser appear non-automated.
5. Navigates to the reviews page and waits for review content to appear, with a two-stage fallback wait to accommodate WAF-induced page reloads.
6. Cleans and extracts the movie title from the page's `<title>` tag.
7. Attempts up to **20 "load more" button clicks**, checking after each click whether the accumulated container count has reached `max_reviews` before deciding to continue. Each click may expose approximately 25 additional reviews, supporting a theoretical maximum of ~500 reviews per call.
8. Queries the DOM using `article.user-review-item` as the canonical container selector, targeting IMDb's modern UI exclusively.
9. For each review container, extracts the review text, numeric rating (1–10), and review date using prioritized fallback selectors.
10. Filters out containers with no text or fewer than 20 characters of review text.
11. Closes the browser and returns all collected reviews.

#### Parameters

| Parameter | Type | Default | Description |
|---|---|---|---|
| `movie_id` | `str` | *(required)* | The IMDb title identifier (e.g., `"tt0111161"` for *The Shawshank Redemption*). Used directly in URL construction: `https://www.imdb.com/title/{movie_id}/reviews/`. |
| `max_reviews` | `int` | `100` | The maximum number of reviews to return. Governs the "load more" loop exit condition (checked against live container count before each click) and the final container iteration slice (`containers[:max_reviews]`). |

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
- **Timing dependencies**: Uses `wait_for_timeout` (wall-clock sleeps) to accommodate WAF challenge resolution and "load more" animation. Total execution time can range from several seconds to well over a minute depending on network conditions, WAF behavior, and the number of "load more" clicks performed. Each click now incurs a 2-second wait (up from 1.5 seconds), and up to 20 clicks can be performed.
- **No persistent state**: The browser and context are fully created and destroyed within each function call. No cookies, sessions, or cache are persisted between calls.
- **No error propagation**: Most internal exceptions are silently caught and swallowed. The function will return a partial or empty list rather than raising an exception in most failure scenarios.

#### Internal Selector Strategy

**"Load more" button detection** (current implementation):

The function now uses Playwright's `locator` API with a compiled regular expression to identify the load-more button, rather than querying by CSS class or `data-testid` attribute:

```python
import re as _re
load_more = page.locator('button', has_text=_re.compile(r'^\d+ more$'))
```

This matches button text of the form `"25 more"`, `"50 more"`, etc. If no such button exists, the loop exits immediately.

**Container selection** (single authoritative selector):

```
article.user-review-item    ← Modern IMDb UI (sole selector)
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

### Summary

This commit makes two coordinated changes to `scrape_imdb_reviews_playwright`: it raises the default `max_reviews` cap and substantially redesigns the "load more" pagination loop. The container extraction strategy is also simplified by removing legacy UI fallbacks.

---

### Change 1: Default `max_reviews` Increased from `75` to `100`

```diff
- def scrape_imdb_reviews_playwright(movie_id: str, max_reviews: int = 75) -> list[dict]:
+ def scrape_imdb_reviews_playwright(movie_id: str, max_reviews: int = 100) -> list[dict]:
```

**What changed:** The default value of the `max_reviews` parameter was raised from `75` to `100`.

**Why it matters:** Any caller that invokes `scrape_imdb_reviews_playwright(movie_id)` without explicitly passing `max_reviews` will now receive up to 100 reviews instead of 75. This is a **public API behavioral change** affecting all call sites that rely on the default. Callers that always pass an explicit `max_reviews` value are unaffected.

---

### Change 2: Pagination Loop Overhauled

**Before:**

```python
# Try to load more reviews if button exists
for _ in range(3):  # up to 3 load-more clicks
    if len(reviews) >= max_reviews:
        break
    try:
        btn = page.query_selector('button.ipc-btn--see-more, [data-testid="load-more-btn"]')
        if btn:
            btn.click()
            page.wait_for_timeout(1500)
    except Exception:
        break
```

**After:**

```python
# Click load-more until we have enough review containers or button disappears
# The button text matches "\d+ more" (e.g. "25 more")
import re as _re
for _ in range(20):  # up to 20 clicks (~25 reviews each = ~500 max)
    containers_so_far = page.query_selector_all('article.user-review-item')
    if len(containers_so_far) >= max_reviews:
        break
    try:
        load_more = page.locator('button', has_text=_re.compile(r'^\d+ more$'))
        if load_more.count() == 0:
            break
        load_more.first.click()
        page.wait_for_timeout(2000)
    except Exception:
        break
```

**What changed — in detail:**

| Aspect | Before | After |
|---|---|---|
| Maximum clicks | 3 | 20 |
| Theoretical max reviews loadable | ~75–100 | ~500 |
| Early-exit guard | `len(reviews) >= max_reviews` (always `0` at this point — **bug**) | `len(containers_so_far) >= max_reviews` (counts actual DOM containers — **correct**) |
| Button selector strategy | CSS class / `data-testid` attribute | `locator()` with regex matching button text `^\d+ more$` |
| Button absence handling | `if btn:` guard (no `break`) | `if load_more.count() == 0: break` (exits loop cleanly) |
| Wait time per click | `1500` ms | `2000` ms |

**Bug fix:** The previous implementation checked `len(reviews) >= max_reviews` as the loop guard, but `reviews` was always an empty list at that point in the code (reviews are only appended later, during container iteration). This meant the guard never triggered, and the loop always ran all 3 iterations unconditionally. The new implementation correctly queries live DOM containers (`page.query_selector_all('article.user-review-item')`) and checks the actual number of loaded review elements, making the early-exit logic functional.

**Button detection improvement:** The old code targeted specific CSS classes (`button.ipc-btn--see-more`) and `data-testid` attributes (`[data-testid="load-more-btn"]`), both of which are fragile against IMDb UI updates. The new code uses a regex match on visible button text (`^\d+ more$`), which is more robust to class name and attribute changes while still being specific enough to avoid false matches.

**Capacity increase:** Expanding from 3 to 20 clicks dramatically increases the maximum number of reviews the function can retrieve in a single call. With approximately 25 reviews per click, the new ceiling is around 500 reviews, compared to roughly 75–100 previously.

---

### Change 3: Container Selector Simplified

**Before:**

```python
containers = (
    page.query_selector_all('article.user-review-item') or
    page.query_selector_all('div[data-testid="review-card"]') or
    page.query_selector_all('div.lister-item-content') or
    page.query_selector_all('article')
)
```

**After:**

```python
containers = page.query_selector_all('article.user-review-item')
```

**What changed:** The cascading fallback chain of four alternative container selectors was replaced with a single authoritative selector: `article.user-review-item`.

**Why it matters:** This change narrows compatibility to IMDb's modern UI exclusively. The removed selectors (`div[data-testid="review-card"]`, `div.lister-item-content`, and the generic `article`) targeted IMDb's legacy UI layouts. Removing them means:

- The function is simpler and easier to reason about.
- If IMDb's modern UI is not present (e.g., an A/B test serves the legacy UI, or selectors change), the function will return `[]` rather than falling back to an alternative layout.
- The pagination loop already uses `article.user-review-item` for its container count, so using the same selector for extraction is now consistent throughout the function.

This is a **behavioral narrowing**: the function trades broad UI compatibility for simplicity and consistency.

---

## 4. Dependencies & Integration

### External Dependencies

| Dependency | Import | Purpose |
|---|---|---|
| `playwright` | `from playwright.sync_api import sync_playwright` | Browser automation. Requires the `playwright` Python package and the Chromium browser binary (installed via `playwright install chromium`). |
| `re` | `import re as _re` *(inline, inside function body)* | Compiles the regular expression used to match the "load more" button text (`^\d+ more$`). Imported at function call time rather than module level. |

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

- **Default behavior change**: Callers relying on the default `max_reviews` value will now receive up to 100 reviews per call instead of 75. If downstream systems have size constraints (e.g., payload limits, processing budgets), they should be reviewed.
- **Increased execution time**: The pagination loop now supports up to 20 clicks at 2 seconds each, compared to 3 clicks at 1.5 seconds previously. Worst-case blocking time for the pagination phase alone has increased from ~4.5 seconds to ~40 seconds. In an async web framework (e.g., FastAPI), this function **must** be run in a thread pool executor to avoid blocking the event loop.
- **Thread safety**: Each call creates and destroys its own browser instance. Multiple concurrent calls will spawn multiple Chromium processes, which may exhaust system resources. A semaphore or task queue is strongly recommended for production use.
- **No caching**: Results are not cached. Repeated calls with the same `movie_id` will make full browser round-trips each time.
- **No retry logic**: Beyond the two-stage WAF wait, there is no retry mechanism. Transient failures produce empty results silently. Callers cannot distinguish between a network failure, a WAF block, and a movie with zero reviews — all return `[]`.
- **Legacy UI compatibility removed**: The container selector fallback chain has been removed. If IMDb serves its legacy UI for any reason, the function will return `[]` silently.

---

`FUNCTIONAL_CHANGE: YES`
