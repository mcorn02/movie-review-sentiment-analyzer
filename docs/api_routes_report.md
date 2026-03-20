# `api/routes/report.py` — Technical Documentation

## 1. Module Overview

### Purpose

`api/routes/report.py` implements the SSE (Server-Sent Events) streaming endpoint for the movie report pipeline. It is the primary HTTP entry point for clients that want to trigger a full movie review analysis — from scraping through sentiment analysis to report generation — and receive real-time progress updates as the pipeline executes.

### Responsibilities

- **Input validation**: Verifies that the submitted URL matches the expected IMDB title URL pattern (using a module-level compiled regex) and that a valid movie ID can be extracted from it.
- **Pipeline orchestration**: Coordinates three sequential stages — scraping, sentiment analysis, and report generation — delegating actual work to service-layer modules.
- **Real-time progress streaming**: Uses an `asyncio.Queue` as an internal message bus to bridge the async report pipeline with the SSE response stream, allowing nested async callbacks to communicate back to the HTTP response generator without violating Python's generator yield semantics.
- **SSE event formatting**: Serializes all structured data as properly formatted SSE frames and assigns semantic event types so clients can route each message appropriately.
- **Error handling and graceful degradation**: Emits `error` and `warning` SSE events on failure conditions (scraping failures of any exception type, insufficient reviews, report generation exceptions) rather than terminating the stream silently. A `done` event is always emitted at stream termination.

### Position in the System

```
Client (browser / frontend)
        │  POST /report/imdb
        ▼
api/routes/report.py          ← this module
        │
        ├── app.scraper_service   (blocking I/O, run in thread pool)
        └── app.report_generator  (async pipeline, sentiment + LLM)
```

This module sits at the API boundary layer. It is a FastAPI `APIRouter` mounted under the `/report` prefix and tagged `"report"` for OpenAPI grouping. It depends exclusively on service/application-layer modules and contains no business logic itself.

---

## 2. Key Components

### 2.1 Module-Level Router

```python
router = APIRouter(prefix="/report", tags=["report"])
```

A FastAPI `APIRouter` instance. All routes defined in this module are prefixed with `/report`. The `"report"` tag groups these endpoints in the generated OpenAPI/Swagger UI documentation. This router must be registered with the main FastAPI `app` instance (typically in `api/main.py` or equivalent) via `app.include_router(router)`.

---

### 2.2 Module-Level Constant: `IMDB_URL_RE`

```python
IMDB_URL_RE = re.compile(r"imdb\.com/title/tt\d+", re.I)
```

A pre-compiled, case-insensitive regular expression pattern used to validate that submitted URLs follow the expected IMDB title URL format (e.g., `https://www.imdb.com/title/tt1234567/`).

Compiling this at module level (rather than inside the request handler) is a performance and design improvement: the regex is compiled once at import time and reused across all requests, rather than being recompiled on every invocation.

---

### 2.3 `_sse_event`

```python
def _sse_event(event: str, data: dict) -> str
```

#### What it does
Formats a single Server-Sent Event frame as a string conforming to the [SSE specification](https://developer.mozilla.org/en-US/docs/Web/API/Server-sent_events/Using_server-sent_events).

#### Parameters

| Parameter | Type   | Description                                                        |
|-----------|--------|--------------------------------------------------------------------|
| `event`   | `str`  | The SSE event name (e.g., `"stage"`, `"error"`, `"done"`)         |
| `data`    | `dict` | A JSON-serializable dictionary to be sent as the event payload     |

#### Returns
`str` — A correctly formatted SSE string with the structure:
```
event: <event>
data: <json_payload>

```
(Note the trailing double newline, which is required by the SSE specification to delimit event boundaries.)

#### Side Effects / Dependencies
- Calls `json.dumps` on `data`. Will raise `TypeError` if `data` contains non-JSON-serializable values.
- No I/O or state mutation.
- Private (prefixed with `_`); not intended to be called outside this module.

#### Example Output
```
event: stage
data: {"stage": "scraping", "message": "Scraping reviews from IMDB for tt1234567..."}

```

---

### 2.4 `imdb_report`

```python
@router.post("/imdb")
async def imdb_report(request: IMDBReportRequest) -> StreamingResponse
```

#### What it does
The sole public HTTP handler in this module. Accepts a POST request containing an IMDB movie URL, validates it, and returns a `StreamingResponse` that streams Server-Sent Events to the client across the full lifecycle of the report pipeline.

Internally, it defines and immediately passes an `event_stream()` async generator to `StreamingResponse`, which drives the entire pipeline through three logical stages.

#### Parameters

| Parameter | Type                | Source       | Description                                                        |
|-----------|---------------------|--------------|--------------------------------------------------------------------|
| `request` | `IMDBReportRequest` | Request body | Pydantic model containing `imdb_url: str` and optional `aspects`   |

#### Returns
`StreamingResponse` with:
- `media_type="text/event-stream"`
- Headers:
  - `Cache-Control: no-cache`
  - `Connection: keep-alive`
  - `X-Accel-Buffering: no` (prevents Nginx reverse proxy from buffering the stream)

#### Raises (before streaming begins)

| Condition                                          | HTTP Status | Detail                                                         |
|----------------------------------------------------|-------------|----------------------------------------------------------------|
| URL does not match `imdb\.com/title/tt\d+`         | `400`       | `"Please enter a valid IMDB movie URL (imdb.com/title/tt...)"` |
| `extract_movie_id` raises `ValueError`             | `400`       | Exception message propagated from `extract_movie_id`          |

> **Important**: Once the `StreamingResponse` is returned, subsequent errors are communicated as SSE `error` events rather than HTTP error codes, because the HTTP response headers have already been sent to the client.

#### Aspects Resolution

```python
aspects = request.aspects or DEFAULT_ASPECTS
```

If the client does not supply an `aspects` list, the module falls back to `DEFAULT_ASPECTS` from `app.config`.

---

### 2.5 Inner: `event_stream` (async generator)

```python
async def event_stream() -> AsyncGenerator[str, None]
```

Defined inside `imdb_report`. This is the core SSE generator that drives the pipeline and yields formatted SSE strings. It is passed directly to `StreamingResponse`.

#### Pipeline Stages

##### Stage 1 — Scraping

1. Yields a `stage` event with `"stage": "scraping"` to notify the client that scraping has begun.
2. Calls `scrape_imdb_reviews(movie_id, 75)` in a thread pool via `asyncio.to_thread` (non-blocking), requesting up to 75 reviews.
3. On **any exception** (broad `except Exception`): yields `error` + `done` events, then returns.
4. If no reviews are returned: yields `error` + `done` events with a user-friendly message, then returns.
5. Extracts `review_texts` (list of non-empty review strings) and `movie_title` from the returned data.
6. Yields a second `stage` event reporting the count of successfully scraped reviews and the resolved movie title.
7. If fewer than 10 reviews are found, yields a `warning` event advising that results may be less reliable.

##### Stage 2 & 3 — Analysis + Report Generation

Uses an `asyncio.Queue` (`event_queue`) as an internal message bus, because nested async callbacks cannot directly `yield` from the outer generator.

1. Defines `on_stage(stage, data)` callback — called by `async_generate_report` during execution.
2. Defines `run_report()` coroutine that calls `async_generate_report`, places its result or any exception in the queue, and always signals completion via `("_done", None)` in a `finally` block.
3. Launches `run_report()` as a background task via `asyncio.create_task`.
4. Drains the queue in a `while True` loop, yielding each SSE event to the client, until `"_done"` is dequeued.
5. Awaits the background task to ensure it is fully complete before proceeding.

##### Final Output Events

After the pipeline completes successfully:
1. **`charts`** event: sends per-aspect sentiment distribution with both raw counts and percentages.
2. **`report`** event: sends `overall_summary`, `movie_title`, `n_reviews`, and the full `aspects` data array.
3. **`done`** event with `"status": "complete"`.

If `report_result` is `None` after the queue drains (i.e., an error was enqueued), yields `done` with `"status": "error"` and returns without emitting `charts` or `report` events.

---

### 2.6 Inner: `on_stage` (async callback)

```python
async def on_stage(stage: str, data: dict = None) -> None
```

Defined inside `event_stream`. Acts as the progress callback passed to `async_generate_report`. Since it cannot `yield` directly into the outer generator, it uses `event_queue.put_nowait` to enqueue SSE events for the queue-draining loop to consume and yield.

| `stage` value       | Action                                                             |
|---------------------|--------------------------------------------------------------------|
| `"analyzing"`       | Enqueues a `stage` event with a formatted progress message and all `data` fields spread in |
| `"generating"`      | Enqueues a `stage` event signaling that report generation has begun |
| `"aspect_complete"` | Enqueues an `aspect_complete` event with the aspect result data    |

---

### 2.7 Inner: `run_report` (async coroutine)

```python
async def run_report() -> None
```

Defined inside `event_stream`. Wraps `async_generate_report` and communicates its result or failure back to the streaming loop via the queue.

| Queue message          | Condition                                          |
|------------------------|----------------------------------------------------|
| `("_result", report)`  | Successful completion of `async_generate_report`   |
| `("error", {...})`     | Any unhandled exception during report generation   |
| `("_done", None)`      | Always emitted (via `finally`), signals loop exit  |

---

### 2.8 SSE Event Taxonomy

The module establishes a typed SSE event vocabulary consumed by the client:

| Event Type        | When Emitted                                  | Payload Fields                                                        | Client Purpose                           |
|-------------------|-----------------------------------------------|-----------------------------------------------------------------------|------------------------------------------|
| `stage`           | At each pipeline stage transition             | `stage`, `message`, optionally `progress`, `total`, `movie_title`     | Progress bar / status indicator updates  |
| `warning`         | When review count is low (< 10)               | `message`                                                             | Display reliability warning to user      |
| `error`           | On scraping failure or generation exception   | `message`                                                             | Show error state to user                 |
| `aspect_complete` | After each aspect is analyzed                 | Aspect-specific data from `async_generate_report`                     | Incremental aspect card rendering        |
| `charts`          | After all aspects are complete                | `distributions` (array of per-aspect count and percentage data)       | Render chart visualizations              |
| `report`          | When the full report is ready                 | `overall_summary`, `movie_title`, `n_reviews`, `aspects`              | Display the complete report              |
| `done`            | At stream termination (success or error)      | `status` (`"complete"` or `"error"`)                                  | Signal client to close `EventSource`     |

---

## 3. What Changed

A diff was provided. The changes in this commit are refactors and minor behavioral adjustments with some user-visible impacts.

### 3.1 Module-Level Regex Compilation (Refactor + Minor Behavioral Change)

**Before:**
```python
# Inside imdb_report, on every request:
url_pattern = re.compile(r"imdb\.com/title/tt\d+", re.I)
if not url_pattern.search(request.imdb_url):
    raise HTTPException(
        status_code=400,
        detail="Invalid IMDB URL. Must contain imdb.com/title/tt...",
    )
```

**After:**
```python
# At module level, compiled once at import time:
IMDB_URL_RE = re.compile(r"imdb\.com/title/tt\d+", re.I)

# Inside imdb_report:
if not IMDB_URL_RE.search(request.imdb_url):
    raise HTTPException(status_code=400, detail="Please enter a valid IMDB movie URL (imdb.com/title/tt...).")
```

**Why it matters:**
- **Performance**: The regex is now compiled once at module import time rather than on every request. For a high-traffic endpoint, this eliminates repeated compilation overhead.
- **User-visible change**: The HTTP 400 error message changed from `"Invalid IMDB URL. Must contain imdb.com/title/tt..."` to `"Please enter a valid IMDB movie URL (imdb.com/title/tt...)."` — the new message is more user-friendly in tone, suitable for display directly in a UI.
- **Named constant**: Promoting the pattern to `IMDB_URL_RE` makes it testable and reusable as a named module-level constant.

### 3.2 Broadened Exception Handling for Scraping (Behavioral Change)

**Before:**
```python
except RuntimeError as e:
    yield _sse_event("error", {"message": str(e)})
```

**After:**
```python
except Exception as e:
    yield _sse_event("error", {"message": str(e)})
```

**Why it matters:**
- Previously, only `RuntimeError` exceptions raised during scraping were caught and converted to SSE `error` events. Any other exception type (e.g., `ConnectionError`, `TimeoutError`, `ValueError`) would propagate unhandled, likely causing the stream to terminate abruptly with no client-visible error event.
- The change to `except Exception` ensures that all scraping failures — regardless of their type — are gracefully reported to the client as structured SSE `error` events followed by a `done` event. This is a meaningful improvement in robustness.

### 3.3 Improved "No Reviews Found" Error Message (User-Visible Change)

**Before:**
```python
"message": f"No reviews found for movie {movie_id}.",
```

**After:**
```python
"message": f"No reviews found for '{movie_id}' on IMDB.",
```

**Why it matters:** Minor UX improvement. The new message adds quotes around the movie ID for clarity and specifies "on IMDB" as the source context, making the message slightly more informative and consistently formatted with similar messages in the module.

### 3.4 Code Cleanup and Comment Removal (Non-Functional)

Several inline comments that restated obvious implementation details were removed:

| Removed Comment                                    | Location                              |
|----------------------------------------------------|---------------------------------------|
| `# Validate URL`                                   | Before URL pattern check              |
| `# Extract review texts and movie title`           | Before list comprehension             |
| `# We can't yield from a nested callback, so we use a queue` | Inside `on_stage`       |
| `# Start the report generation task`               | Before `asyncio.create_task`          |
| `# Stream events from the queue`                   | Before the `while True` loop          |
| `# Ensure task is fully complete` (inline)         | After `await task`                    |
| `# Send the full report`                           | Before the `report` SSE event         |

**Why it matters:** The removal of redundant comments makes the code cleaner and shifts documentation responsibility to this external documentation file. No functional behavior changes.

### 3.5 `on_stage` Callback Cleanup (Refactor)

**Before:**
```python
async def on_stage(stage, data=None):
    if stage == "analyzing":
        yield_data = {
            "stage": "analyzing
