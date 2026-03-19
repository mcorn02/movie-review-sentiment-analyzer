# `api/routes/report.py` — Technical Documentation

## 1. Module Overview

### Purpose

`api/routes/report.py` implements the SSE (Server-Sent Events) streaming endpoint for the IMDB movie report pipeline. It is the primary HTTP entry point for clients that want to trigger a full movie review analysis — from scraping through sentiment analysis to report generation — and receive real-time progress updates as the pipeline executes.

### Responsibilities

- **Input validation**: Verifies that the submitted URL matches the expected IMDB title URL pattern and that a valid movie ID can be extracted.
- **Pipeline orchestration**: Coordinates three sequential stages — scraping, sentiment analysis, and report generation — delegating the actual work to service-layer modules.
- **Real-time progress streaming**: Uses an `asyncio.Queue` as an internal message bus to bridge the async report pipeline with the SSE response stream, allowing nested async callbacks to communicate back to the HTTP response generator.
- **SSE event formatting**: Serializes all structured data as properly formatted SSE frames and assigns semantic event types so clients can route each message appropriately.
- **Error handling and graceful degradation**: Emits error and warning SSE events on failure conditions (scraping failures, insufficient reviews, report generation exceptions) rather than terminating the stream silently.

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

This module sits at the API boundary layer. It is a FastAPI `APIRouter` mounted under the `/report` prefix and tagged `"report"` for OpenAPI grouping. It depends exclusively on service/application-layer modules and does not contain business logic itself.

---

## 2. Key Components

### 2.1 Module-Level Router

```python
router = APIRouter(prefix="/report", tags=["report"])
```

A FastAPI `APIRouter` instance. All routes defined in this module are prefixed with `/report`. The `"report"` tag groups these endpoints in the generated OpenAPI/Swagger UI documentation. This router must be registered with the main FastAPI `app` instance (typically in `api/main.py` or equivalent) via `app.include_router(router)`.

---

### 2.2 `_sse_event`

```python
def _sse_event(event: str, data: dict) -> str
```

#### What it does
Formats a single Server-Sent Event frame as a string conforming to the [SSE specification](https://developer.mozilla.org/en-US/docs/Web/API/Server-sent_events/Using_server-sent_events).

#### Parameters

| Parameter | Type   | Description                                           |
|-----------|--------|-------------------------------------------------------|
| `event`   | `str`  | The SSE event name (e.g., `"stage"`, `"error"`, `"done"`) |
| `data`    | `dict` | A JSON-serializable dictionary to be sent as the event payload |

#### Returns
`str` — A correctly formatted SSE string with the structure:
```
event: <event>\ndata: <json_payload>\n\n
```

#### Side Effects / Dependencies
- Calls `json.dumps` on `data`. Will raise `TypeError` if `data` contains non-serializable values.
- No I/O or state mutation.
- Private (prefixed with `_`); not intended to be called outside this module.

#### Example Output
```
event: stage
data: {"stage": "scraping", "message": "Scraping reviews from IMDB for tt1234567..."}

```

---

### 2.3 `imdb_report`

```python
@router.post("/imdb")
async def imdb_report(request: IMDBReportRequest) -> StreamingResponse
```

#### What it does
The sole public HTTP handler in this module. Accepts a POST request containing an IMDB movie URL, validates it, and returns a `StreamingResponse` that streams Server-Sent Events to the client across the full lifecycle of the report pipeline.

Internally, it defines and immediately invokes an `event_stream()` async generator that drives the entire pipeline through three logical stages.

#### Parameters

| Parameter | Type                | Source       | Description                                           |
|-----------|---------------------|--------------|-------------------------------------------------------|
| `request` | `IMDBReportRequest` | Request body | Pydantic model containing `imdb_url` and optional `aspects` |

#### Returns
`StreamingResponse` with:
- `media_type="text/event-stream"`
- Headers: `Cache-Control: no-cache`, `Connection: keep-alive`, `X-Accel-Buffering: no`

#### Raises (before streaming begins)
| Condition | HTTP Status | Detail |
|-----------|-------------|--------|
| URL does not match `imdb\.com/title/tt\d+` | `400` | `"Invalid IMDB URL. Must contain imdb.com/title/tt..."` |
| `extract_movie_id` raises `ValueError` | `400` | Exception message from `extract_movie_id` |

> **Note**: Once the `StreamingResponse` is returned, subsequent errors are communicated as SSE `error` events rather than HTTP error codes, because the HTTP response headers have already been sent.

#### Aspects Resolution
```python
aspects = request.aspects or DEFAULT_ASPECTS
```
If the client does not supply an `aspects` list, the module falls back to `DEFAULT_ASPECTS` from `app.config`.

---

### 2.4 Inner: `event_stream` (async generator)

```python
async def event_stream() -> AsyncGenerator[str, None]
```

Defined inside `imdb_report`. This is the core SSE generator that drives the pipeline and yields formatted SSE strings. It is passed directly to `StreamingResponse`.

#### Pipeline Stages

##### Stage 1 — Scraping
1. Emits a `stage` event with `"stage": "scraping"` to notify the client that scraping has begun.
2. Calls `scrape_imdb_reviews(movie_id, 75)` in a thread pool via `asyncio.to_thread` (non-blocking).
3. On `RuntimeError`: emits `error` + `done` events, then returns.
4. If no reviews are returned: emits `error` + `done` events, then returns.
5. Extracts `review_texts` (list of non-empty strings) and `movie_title` from results.
6. Emits a second `stage` event reporting the count of scraped reviews and the movie title.
7. If fewer than 10 reviews are found, emits a `warning` event.

##### Stage 2 & 3 — Analysis + Report Generation
Uses an `asyncio.Queue` (`event_queue`) as an internal message bus, because nested async callbacks cannot directly `yield` from the outer generator.

1. Defines `on_stage(stage, data)` callback — called by `async_generate_report` during analysis:
   - `"analyzing"` → puts `("stage", {...})` in queue with progress details.
   - `"generating"` → puts `("stage", {...})` in queue signaling report generation.
   - `"aspect_complete"` → puts `("aspect_complete", data)` in queue.
2. Defines `run_report()` coroutine that calls `async_generate_report`, then puts the result or error into the queue, and always signals completion with `("_done", None)`.
3. Launches `run_report()` as a background task via `asyncio.create_task`.
4. Drains the queue in a `while True` loop, yielding each SSE event, until `"_done"` is received.
5. Awaits the task to ensure full completion.

##### Final Output Events
After the pipeline completes:
1. **`charts`** event: sends per-aspect sentiment distribution (counts and percentages).
2. **`report`** event: sends `overall_summary`, `movie_title`, `n_reviews`, and full `aspects` data.
3. **`done`** event with `"status": "complete"`.

---

### 2.5 Inner: `on_stage` (async callback)

```python
async def on_stage(stage: str, data: dict = None) -> None
```

Defined inside `event_stream`. Acts as the progress callback passed to `async_generate_report`. Because it cannot `yield` into the outer generator directly, it uses `event_queue.put_nowait` to enqueue SSE events for the queue-draining loop.

| `stage` value      | Action                                                   |
|--------------------|----------------------------------------------------------|
| `"analyzing"`      | Enqueues a `stage` event with formatted progress message |
| `"generating"`     | Enqueues a `stage` event with generating message         |
| `"aspect_complete"`| Enqueues an `aspect_complete` event with aspect data     |

---

### 2.6 Inner: `run_report` (async coroutine)

```python
async def run_report() -> None
```

Defined inside `event_stream`. Wraps `async_generate_report` and communicates its result (or failure) back to the streaming loop via the queue.

| Queue message         | Condition                         |
|-----------------------|-----------------------------------|
| `("_result", report)` | Successful report generation      |
| `("error", {...})`    | Any unhandled exception           |
| `("_done", None)`     | Always (via `finally`)            |

---

## 3. What Changed

This entire file was **newly added** in this commit (`new file mode 100644`). There is no prior version to diff against behaviorally; this is the initial implementation of the `/report/imdb` endpoint.

### What Was Added

#### New FastAPI Router and Endpoint
- A new `APIRouter` mounted at `/report` was introduced, establishing the `POST /report/imdb` route as a first-class API endpoint.

#### SSE Streaming Architecture
- The response uses `StreamingResponse` with `media_type="text/event-stream"` rather than a conventional JSON response. This is a deliberate architectural choice to allow long-running pipeline operations (scraping, LLM analysis) to report progress in real time without requiring polling.

#### Async Queue-Based Event Bridge
- The `asyncio.Queue` pattern solves a fundamental Python async limitation: async generators cannot yield from nested coroutines or callbacks. The queue decouples the `on_stage` callback (called deep inside the report generator) from the SSE-yielding outer generator, enabling clean bidirectional communication.

#### Structured SSE Event Taxonomy
The module establishes a typed SSE event vocabulary:

| Event Type       | When Emitted                                | Client Purpose                          |
|------------------|---------------------------------------------|-----------------------------------------|
| `stage`          | At each pipeline stage transition           | Progress bar / status indicator updates |
| `warning`        | When review count is low (< 10)             | Display reliability warning             |
| `error`          | On scraping failure or generation exception | Show error state to user                |
| `aspect_complete`| After each aspect is analyzed               | Incremental aspect card rendering       |
| `charts`         | After all aspects complete                  | Render chart visualizations             |
| `report`         | When full report is ready                   | Display complete report                 |
| `done`           | At stream termination (success or error)    | Signal client to close EventSource      |

#### Nginx-Compatible Headers
The `X-Accel-Buffering: no` header is specifically added to prevent Nginx (commonly used as a reverse proxy) from buffering the SSE stream, which would defeat the real-time streaming purpose.

#### Graceful Error Boundaries
Error handling distinguishes between:
- **Pre-stream errors** (invalid URL, bad movie ID) → standard HTTP 400 responses
- **In-stream errors** (scraping failure, generation exception) → SSE `error` events followed by `done` with `"status": "error"`

This means clients always receive a `done` event regardless of success or failure, giving them a reliable termination signal.

#### Blocking I/O Offload
`scrape_imdb_reviews` (a synchronous, blocking scraper) is wrapped with `asyncio.to_thread`, preventing it from blocking the FastAPI event loop during the potentially long scraping operation.

---

## 4. Dependencies & Integration

### Imports From

| Import | Source | Role |
|--------|--------|------|
| `asyncio` | Python stdlib | Thread offloading (`to_thread`), queue, task creation |
| `json` | Python stdlib | SSE payload serialization |
| `re` | Python stdlib | IMDB URL pattern validation |
| `APIRouter`, `HTTPException` | `fastapi` | Route registration, HTTP error responses |
| `StreamingResponse` | `fastapi.responses` | SSE HTTP response wrapper |
| `IMDBReportRequest` | `api.models` | Pydantic request body model (contains `imdb_url: str`, `aspects: list \| None`) |
| `DEFAULT_ASPECTS` | `app.config` | Fallback list of sentiment aspects when none are provided by client |
| `extract_movie_id` | `app.scraper_service` | Parses IMDB movie ID (e.g., `tt1234567`) from a URL string |
| `scrape_imdb_reviews` | `app.scraper_service` | Synchronous IMDB review scraper; returns list of review dicts |
| `async_generate_report` | `app.report_generator` | Async pipeline: aspect sentiment analysis + summary generation |

### Expected Interfaces

#### `IMDBReportRequest` (from `api.models`)
Must expose:
- `.imdb_url: str`
- `.aspects: list[str] | None`

#### `scrape_imdb_reviews(movie_id: str, max_reviews: int) -> list[dict]`
Must return a list of dicts with at least:
- `"review_text": str`
- `"movie_title": str`

#### `async_generate_report(review_texts, aspects, on_stage) -> dict`
Must return a dict with:
- `"overall_summary": str`
- `"n_reviews": int`
- `"aspects": list[dict]` where each aspect dict contains `"name"` and `"distribution"` (with `"positive"`, `"negative"`, `"not_mentioned"` sub-dicts each having `"count"` and `"pct"`)

Must call `on_stage(stage: str, data: dict)` during execution.

### What Depends on This Module

- **FastAPI application entry point** (e.g., `api/main.py`): must import `router` from this module and register it via `app.include_router(router)`.
- **Frontend / client code**: consumes the `POST /report/imdb` endpoint and must implement an `EventSource` or equivalent SSE client that handles all defined event types (`stage`, `warning`, `error`, `aspect_complete`, `charts`, `report`, `done`).
- **OpenAPI documentation**: FastAPI automatically generates endpoint documentation for `/report/imdb` based on this router's metadata and the `IMDBReportRequest` model schema.

---

`FUNCTIONAL_CHANGE: YES`
