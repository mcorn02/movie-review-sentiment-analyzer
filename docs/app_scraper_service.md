# `app/scraper_service.py` — Technical Documentation

---

## 1. Module Overview

`scraper_service.py` is the **service layer** responsible for orchestrating IMDB review scraping within the application. It acts as the bridge between the higher-level application logic (e.g., a FastAPI route handler) and the lower-level Scrapy spider defined in `app/imdb_scraper.py`.

### Purpose

The module solves a fundamental architectural problem: **Scrapy's Twisted reactor cannot be started more than once per process**, and it is incompatible with FastAPI's own `asyncio`-based event loop. To work around this, `scraper_service.py` isolates every scraping run inside a **fresh Python subprocess**, completely sidestepping any reactor lifecycle conflicts.

### Responsibilities

| Responsibility | Function |
|---|---|
| Parse and validate an IMDB URL to extract a canonical movie ID | `extract_movie_id` |
| Launch a Scrapy spider in an isolated subprocess | `scrape_imdb_reviews` |
| Configure Scrapy settings programmatically at runtime | (inline within `scrape_imdb_reviews`) |
| Read and deserialize the spider's JSON output | (inline within `scrape_imdb_reviews`) |
| Surface meaningful errors for known failure modes (403, timeout, non-zero exit) | (inline within `scrape_imdb_reviews`) |

### Position in the System

```
FastAPI Route Handler
       │
       ▼
scraper_service.py          ← YOU ARE HERE
  ├── extract_movie_id()    (URL parsing utility)
  └── scrape_imdb_reviews() (subprocess orchestrator)
             │
             ▼ subprocess
       app/imdb_scraper.py
       IMDBReviewSpider (Scrapy + Twisted)
             │
             ▼
        IMDB Website
             │
             ▼
        reviews.json (temp file, cleaned up automatically)
```

---

## 2. Key Components

### 2.1 `extract_movie_id`

```python
def extract_movie_id(imdb_url: str) -> str:
```

#### Description

Parses an IMDB URL (or any string) and extracts the **IMDB title ID** — the alphanumeric token of the form `tt` followed by one or more digits (e.g., `tt1375666`).

The function uses a regular expression search rather than strict URL parsing, so it is tolerant of different URL formats (full URLs, path-only strings, etc.), as long as the `tt\d+` pattern appears somewhere in the input.

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

The primary entry point for scraping IMDB reviews. This function:

1. Creates a **temporary directory** (automatically cleaned up on exit).
2. **Dynamically builds** a self-contained Python script as a string that configures and runs the `IMDBReviewSpider` Scrapy spider via `CrawlerProcess`.
3. Executes that script as a **subprocess** using the current Python interpreter (`sys.executable`), capturing stdout/stderr.
4. Reads and deserializes the JSON output written by the spider to a temp file.
5. Returns the parsed review data, or an empty list if nothing was scraped.

The subprocess isolation ensures that Scrapy's Twisted reactor does not interfere with the parent process's event loop (FastAPI/asyncio).

#### Parameters

| Parameter | Type | Default | Description |
|---|---|---|---|
| `movie_id` | `str` | *(required)* | A valid IMDB title ID (e.g., `"tt1375666"`). Typically obtained via `extract_movie_id()`. |
| `max_reviews` | `int` | `75` | The maximum number of reviews to scrape. Passed directly to `IMDBReviewSpider`. |

#### Return Value

| Type | Description |
|---|---|
| `list[dict]` | A list of review dictionaries. Each dict contains the following keys (as defined by the spider): `movie_id`, `movie_title`, `review_text`, `rating`, `review_date`, `source`. Returns an empty list `[]` if the spider produced no output or wrote an empty file. |

#### Raises

| Exception | Condition |
|---|---|
| `RuntimeError` | Raised when the subprocess exits with a non-zero return code. If `"403"` appears in stderr, a more specific message about IMDB rate-limiting is raised. Otherwise, a generic message including the exit code and up to 500 characters of stderr is raised. |
| `subprocess.TimeoutExpired` | Implicitly raised (not caught) if the subprocess does not complete within **120 seconds**. |

#### Subprocess Script Configuration

The dynamically generated script configures the spider with the following Scrapy settings:

| Setting | Value | Purpose |
|---|---|---|
| `FEEDS` | `{output_file: {format: "json", encoding: "utf8", overwrite: True}}` | Write scraped items to the temp JSON file |
| `AUTOTHROTTLE_ENABLED` | `True` | Enable adaptive throttling to be polite to IMDB |
| `AUTOTHROTTLE_TARGET_CONCURRENCY` | `2.0` | Target 2 concurrent requests on average |
| `DOWNLOAD_DELAY` | `0.3` | Minimum delay (seconds) between requests |
| `USER_AGENT` | Chrome 120 on macOS string | Mimic a real browser to reduce bot detection |
| `HTTPERROR_ALLOWED_CODES` | `[403, 404]` | Pass 403/404 responses to the spider rather than dropping them |
| `LOG_LEVEL` | `"WARNING"` | Suppress verbose Scrapy output |
| `REQUEST_FINGERPRINTER_IMPLEMENTATION` | `"2.7"` | Use the modern fingerprinter to silence deprecation warnings |

#### Side Effects

- **Creates a temporary directory** on the filesystem (inside the OS temp location). This directory and all its contents, including `reviews.json`, are **automatically deleted** when the `with tempfile.TemporaryDirectory()` block exits — regardless of success or failure.
- **Spawns a child process** using the current Python interpreter. The child process inherits the current working directory and has access to the same installed packages.
- **Performs network I/O** (within the subprocess) by connecting to `www.imdb.com`.

#### Flow Diagram

```
scrape_imdb_reviews(movie_id, max_reviews)
│
├─ Create TemporaryDirectory
│       └─ output_file = <tmpdir>/reviews.json
│
├─ Build Python script string (f-string with injected values)
│
├─ subprocess.run([sys.executable, "-c", script], timeout=120)
│       └─ Child process:
│               ├─ CrawlerProcess(settings)
│               ├─ process.crawl(IMDBReviewSpider, movie_id_list=[movie_id], max_reviews=max_reviews)
│               └─ process.start()  → writes reviews.json
│
├─ Check returncode
│       ├─ 403 in stderr → raise RuntimeError (rate-limit message)
│       └─ non-zero      → raise RuntimeError (generic message)
│
├─ Check output_file exists → return [] if not
│
├─ Read and JSON-parse output_file
│       └─ empty content → return []
│
└─ return reviews (list[dict])
```

---

## 3. What Changed

This is a **new file** introduced entirely in this commit (`new file mode 100644`). There is no prior version to compare against — the entire module was added from scratch.

### What Was Added

The complete `app/scraper_service.py` module, comprising:

- **Module-level docstring** explaining the Twisted reactor isolation rationale.
- **`extract_movie_id(imdb_url)`** — a URL parsing utility function.
- **`scrape_imdb_reviews(movie_id, max_reviews)`** — the core subprocess-based scraping orchestrator.

### Why the Change Matters Functionally

This module introduces the **only supported mechanism** for running the Scrapy spider within the application. Without it:

- Calling Scrapy's `CrawlerProcess` directly from within a FastAPI async context would raise a `ReactorNotRestartable` error or cause unpredictable behavior on second invocation.
- There would be no standardized interface for translating an IMDB URL into scraped review data.

The subprocess design means:

- Each scraping call is **stateless and isolated** — no shared Twisted reactor state between requests.
- The parent FastAPI process remains **unaffected** by Scrapy's internal event loop management.
- The temporary file mechanism provides a clean, OS-managed data handoff channel between processes.

### Behavioral Characteristics Established by This Commit

- A **120-second hard timeout** is enforced on every scrape operation.
- A **default cap of 75 reviews** per call is set, balancing data richness against latency and rate-limit risk.
- **403 Forbidden responses** receive dedicated error handling with a user-friendly message, since this is the most common failure mode when scraping IMDB.
- Empty or missing output files are treated as **valid empty results** (returning `[]`) rather than errors, accommodating movies with no reviews or failed-but-clean spider runs.

---

## 4. Dependencies & Integration

### Standard Library Imports

| Module | Usage |
|---|---|
| `json` | Deserializes the spider's JSON output file into Python objects |
| `os` | Path construction (`os.path.join`, `os.path.exists`, `os.getcwd`) |
| `re` | Regular expression matching for IMDB title ID extraction |
| `subprocess` | Spawning the isolated Scrapy spider process |
| `sys` | Accessing `sys.executable` to reuse the current interpreter in the subprocess |
| `tempfile` | Creating a self-cleaning temporary directory for the output file |

### Internal Dependencies

| Module | Symbol | How It's Used |
|---|---|---|
| `app/imdb_scraper.py` | `IMDBReviewSpider` | Imported **inside the subprocess script** (not in the parent process). The spider class is crawled by `CrawlerProcess`. |

> ⚠️ Note: The import of `IMDBReviewSpider` occurs only within the dynamically generated subprocess string, not at module load time. This means `scraper_service.py` itself has **no import-time dependency** on `app/imdb_scraper.py`.

### Third-Party Dependencies (in subprocess only)

| Package | Symbol | Usage |
|---|---|---|
| `scrapy` | `CrawlerProcess` | Manages the Twisted reactor and runs the spider to completion |

### What Depends on This Module

This module is intended to be consumed by:

- **FastAPI route handlers** (e.g., in `app/main.py` or a reviews router) that accept an IMDB URL from a client, call `extract_movie_id()` to parse it, then call `scrape_imdb_reviews()` to fetch reviews.
- Potentially **CLI scripts or background task runners** that need to trigger a scrape outside of the HTTP request lifecycle.

### Integration Contract

Callers should expect:

1. `extract_movie_id` to be called first for URL validation before invoking `scrape_imdb_reviews`.
2. `scrape_imdb_reviews` to be a **blocking, synchronous call** — it should be wrapped in `asyncio.run_in_executor` or a thread pool if called from an `async` FastAPI route to avoid blocking the event loop.
3. The returned list items to conform to the schema: `{movie_id, movie_title, review_text, rating, review_date, source}`.

---

`FUNCTIONAL_CHANGE: YES`
