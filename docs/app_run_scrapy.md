# `app/run_scrapy.py` — Module Documentation

---

## 1. Module Overview

**Purpose:**
`run_scrapy.py` is an executable script responsible for orchestrating the scraping of IMDB movie reviews using the Scrapy web crawling framework. It serves as the entry point for the web scraping pipeline within the `app` package.

**Responsibilities:**
- Defining which movie IDs to scrape and how many reviews to collect per movie.
- Configuring the Scrapy `CrawlerProcess` with output, throttling, HTTP, and user-agent settings.
- Launching the `IMDBReviewSpider` spider for the specified movie IDs.
- Writing scraped review data to a local JSON file (`movie_details.json`) in a deterministic, absolute-path location relative to the module itself.
- Providing structured logging throughout the crawl lifecycle.

**Where it fits in the system:**
This module sits at the data-acquisition layer of the application. It is a script-style module (runs top-to-bottom on import/execution) that feeds raw IMDB review data into the rest of the pipeline. The output file (`movie_details.json`) is expected to be consumed by downstream components for processing, analysis, or serving. It depends on `IMDBReviewSpider` (defined in `app/imdb_scraper.py`) to perform the actual HTTP requests and HTML parsing.

> **Note:** This module executes immediately upon being run or imported. It is not designed to be used as an importable library module — it is a standalone execution script.

---

## 2. Key Components

### Constants

---

#### `DYNAMIC_MOVIE_IDS`

```python
DYNAMIC_MOVIE_IDS: list[str] = ["tt30144839"]
```

A list of IMDB title ID strings identifying the movies whose reviews will be scraped. Each ID follows the IMDB standard format (`tt` prefix followed by digits). This list is passed directly to `IMDBReviewSpider` as the `movie_id_list` argument.

- **Type:** `list[str]`
- **Default value:** `["tt30144839"]`
- **Side effects:** Determines the scope of the crawl; adding or removing IDs directly affects how many spiders are spawned and how much data is written to the output file.

---

#### `MAX_REVIEWS`

```python
MAX_REVIEWS: int = 100
```

The maximum number of reviews to scrape per movie. This value is passed to `IMDBReviewSpider` and controls how many review items are collected before the spider stops for a given movie.

- **Type:** `int`
- **Default value:** `100`
- **Side effects:** Directly limits the size of the output dataset per movie.

---

#### `base_dir`

```python
base_dir: str = os.path.dirname(os.path.abspath(__file__))
```

The absolute path to the directory containing this script (`app/`). Computed at module load time to guarantee that the output file path is resolved correctly regardless of the current working directory when the script is invoked.

- **Type:** `str`
- **Side effects:** None; used only to construct `output_file`.

---

#### `output_file`

```python
output_file: str = os.path.join(base_dir, "movie_details.json")
```

The absolute path to the JSON file where scraped review data will be written. Resolves to `<app_directory>/movie_details.json`.

- **Type:** `str`
- **Side effects:** The file at this path is **overwritten** on every run (see `process_settings["FEEDS"]`). Any previously scraped data in this file will be lost.

---

#### `process_settings`

```python
process_settings: dict = {
    "FEEDS": {
        output_file: {
            "format": "json",
            "encoding": "utf8",
            "overwrite": True,
            "indent": 2,
        },
    },
    "ITEM_PIPELINES": {},
    "AUTOTHROTTLE_ENABLED": True,
    "AUTOTHROTTLE_TARGET_CONCURRENCY": 1.0,
    "DOWNLOAD_DELAY": 0.5,
    "AUTOTHROTTLE_DEBUG": False,
    "USER_AGENT": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 ...",
    "HTTPERROR_ALLOWED_CODES": [403, 404],
}
```

A dictionary of Scrapy settings passed to `CrawlerProcess`. Configures the entire crawl environment.

| Setting Key | Value | Purpose |
|---|---|---|
| `FEEDS` | `{output_file: {...}}` | Writes scraped items as pretty-printed, UTF-8 encoded JSON to the absolute output path; overwrites on each run. |
| `ITEM_PIPELINES` | `{}` | Disables all item pipelines; items flow directly to the feed exporter. |
| `AUTOTHROTTLE_ENABLED` | `True` | Enables Scrapy's AutoThrottle extension to adapt download speed based on server response times. |
| `AUTOTHROTTLE_TARGET_CONCURRENCY` | `1.0` | Targets an average of 1 concurrent request to the remote server at a time. |
| `DOWNLOAD_DELAY` | `0.5` | Sets a minimum floor of 0.5 seconds between consecutive requests to the same domain. |
| `AUTOTHROTTLE_DEBUG` | `False` | Suppresses real-time throttle adjustment logging. |
| `USER_AGENT` | Chrome 120 on macOS string | Identifies the crawler as a modern browser to reduce the likelihood of bot-detection blocks. |
| `HTTPERROR_ALLOWED_CODES` | `[403, 404]` | Instructs Scrapy to pass HTTP 403 and 404 responses to the spider rather than dropping them as errors, allowing the spider to handle them explicitly. |

---

#### `process`

```python
process: CrawlerProcess = CrawlerProcess(settings=process_settings)
```

The Scrapy `CrawlerProcess` instance configured with `process_settings`. This object manages the Twisted reactor and coordinates the execution of one or more spiders within a single process.

- **Type:** `scrapy.crawler.CrawlerProcess`
- **Side effects:** Instantiating this object initializes Scrapy's internal logging and reactor infrastructure.

---

### Execution Flow (Module-Level Statements)

The following statements execute sequentially when the module is run:

```python
process.crawl(IMDBReviewSpider, movie_id_list=DYNAMIC_MOVIE_IDS, max_reviews=MAX_REVIEWS)
```
Registers `IMDBReviewSpider` with the `CrawlerProcess`, passing `DYNAMIC_MOVIE_IDS` and `MAX_REVIEWS` as spider arguments. Does **not** start the crawl immediately.

```python
logger.info("Starting Scrapy IMDB Crawl")
logger.info(f"Output will be written to: {output_file}")
process.start()
```
Logs the start of the crawl and the output destination, then **blocks** the current thread by starting the Twisted reactor. The process will not return from `process.start()` until all registered spiders have completed.

```python
logger.info("Scrapy CrawlerProcess finished")
```
Logs a completion message after all spiders have finished and the reactor has stopped.

---

### Logging Configuration

```python
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
```

Configures the root logger at `INFO` level with a timestamped format. A module-level logger named after the module (`app.run_scrapy`) is used for all log statements within this file.

---

## 3. What Changed

### Diff Summary

The only change in this commit is the **removal of a TODO comment**:

```diff
-# TODO: get rid of this web scraping workflow
```

**What was removed:**
A developer-facing inline comment (`# TODO: get rid of this web scraping workflow`) that was located between the import statements and the logging configuration block.

**Why the change matters:**
- This comment signaled a prior intention to deprecate or replace the Scrapy-based scraping workflow entirely. Its removal indicates that this plan has been **abandoned or deferred**, and that the web scraping workflow is now considered a stable, intentional part of the system rather than a temporary or unwanted component.
- The removal cleans up the codebase by eliminating misleading technical debt signals. Other developers reading the code will no longer be prompted to question the legitimacy of this module's existence.

**Behavioral differences:**
None. This is a comment-only change with no effect on runtime behavior, configuration, or output.

---

## 4. Dependencies & Integration

### Imports & External Dependencies

| Dependency | Source | Purpose |
|---|---|---|
| `logging` | Python standard library | Module-level and root logger configuration. |
| `os` | Python standard library | Resolving the absolute path to the output file. |
| `scrapy.crawler.CrawlerProcess` | `scrapy` (third-party) | Manages the Scrapy crawl process and Twisted reactor lifecycle. |
| `IMDBReviewSpider` | `app.imdb_scraper` (internal) | The spider class that implements IMDB review scraping logic. |

### What Depends on This Module

- **`app/imdb_scraper.py`:** Provides `IMDBReviewSpider`, which is the core spider executed by this script. The spider must accept `movie_id_list` and `max_reviews` keyword arguments.
- **Downstream consumers of `movie_details.json`:** Any module, script, or process that reads `app/movie_details.json` is implicitly dependent on this script having been run successfully. Changes to `DYNAMIC_MOVIE_IDS`, `MAX_REVIEWS`, or output formatting in `process_settings` will directly affect the data available to those consumers.
- **Execution environment:** This script assumes a working Scrapy installation, network access to IMDB, and write permissions to the `app/` directory.

### Integration Notes

- This module is designed to be run as a **script** (e.g., `python -m app.run_scrapy`) rather than imported as a library, because all crawl logic executes at module load time.
- The output path is **hardcoded relative to the module file**, making the script location-aware and portable across different working directories.
- Disabling `ITEM_PIPELINES` (`{}`) means no custom data transformation or validation occurs between scraping and file output — all items are written as-is.

---

`FUNCTIONAL_CHANGE: NO`
