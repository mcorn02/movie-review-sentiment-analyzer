# `api/models.py` — Technical Documentation

## 1. Module Overview

**File path:** `api/models.py`

This module defines all **Pydantic request and response models** (schemas) used throughout the API layer. It serves as the single source of truth for data validation, serialization, and deserialization across all API endpoints.

### Responsibilities

- Declares typed request bodies that FastAPI (or equivalent) deserializes and validates from incoming HTTP JSON payloads.
- Declares typed response models that guarantee consistent, documented JSON output shapes returned to API consumers.
- Defines shared enumerations (`AnalysisMethod`, `JobStatus`) used by both request and response models.
- Provides structured intermediate data types (`AspectResult`, `AspectBreakdown`, `PainPoint`, `Report`, etc.) used by the backend pipeline and batch job system.

### Where It Fits in the System

```
HTTP Client
    │
    ▼
API Routes / Endpoints
    │  (use models for request parsing + response shaping)
    ▼
api/models.py  ◄── this file
    │
    ▼
Backend Services / Analyzers / Job Workers
```

All API route handlers depend on this module. It has no dependencies on other internal modules, making it a **foundational, low-level layer** with no circular import risk.

---

## 2. Key Components

### Enumerations

---

#### `AnalysisMethod`

```python
class AnalysisMethod(str, Enum):
    llm = "LLM (OpenAI)"
    nli = "Zero-shot NLI (local)"
```

**What it does:** Enumerates the two supported sentiment analysis backends.

| Member | Value | Description |
|--------|-------|-------------|
| `llm` | `"LLM (OpenAI)"` | Uses the OpenAI API (remote, requires API key) |
| `nli` | `"Zero-shot NLI (local)"` | Uses a local zero-shot Natural Language Inference model |

Inherits from `str`, so members serialize to their string values in JSON.

---

#### `JobStatus`

```python
class JobStatus(str, Enum):
    queued = "queued"
    running = "running"
    done = "done"
    failed = "failed"
```

**What it does:** Represents the lifecycle state of an asynchronous batch analysis job.

| Member | Value | Description |
|--------|-------|-------------|
| `queued` | `"queued"` | Job has been accepted but not yet started |
| `running` | `"running"` | Job is actively processing reviews |
| `done` | `"done"` | Job completed successfully |
| `failed` | `"failed"` | Job encountered a fatal error |

---

### Domain Configuration Models

---

#### `DomainCreate`

```python
class DomainCreate(BaseModel):
    name: str = Field(..., description="Human-readable domain name, e.g. 'restaurant'")
    aspects: list[str] = Field(..., description="Aspects to analyze for this domain")
    description: str | None = Field(None, description="Optional context shown to the LLM")
```

**What it does:** Request body model for creating a new analysis domain configuration.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | `str` | ✅ Yes | Human-readable label for the domain (e.g., `"restaurant"`, `"hotel"`) |
| `aspects` | `list[str]` | ✅ Yes | List of aspects the analysis will evaluate (e.g., `["food", "service", "ambiance"]`) |
| `description` | `str \| None` | ❌ No | Optional free-text context injected into LLM prompts to improve accuracy |

**Side effects / notes:** `description` is passed directly to the LLM when `AnalysisMethod.llm` is used; it should be written as a concise system context string.

---

#### `DomainResponse`

```python
class DomainResponse(DomainCreate):
    id: str
    is_preset: bool
```

**What it does:** Response model returned when reading or creating a domain. Extends `DomainCreate` with server-assigned fields.

| Field | Type | Description |
|-------|------|-------------|
| `id` | `str` | Server-generated unique identifier for the domain |
| `is_preset` | `bool` | `True` if this domain is a built-in preset; `False` if user-created |

Inherits all fields from `DomainCreate`.

---

### Single-Review Analysis Models

---

#### `AnalyzeRequest`

```python
class AnalyzeRequest(BaseModel):
    review: str
    domain_id: str | None = Field(None, description="Use a saved domain config by ID")
    domain: str = Field("product", description="Domain label if not using a saved config")
    aspects: list[str] | None = Field(None, description="Override aspects from domain config")
    method: AnalysisMethod = AnalysisMethod.llm
```

**What it does:** Request body for the single-review sentiment analysis endpoint.

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `review` | `str` | ✅ Yes | — | The raw review text to analyze |
| `domain_id` | `str \| None` | ❌ No | `None` | ID of a saved `DomainResponse`; if provided, the server loads aspects and description from it |
| `domain` | `str` | ❌ No | `"product"` | Fallback domain label used when `domain_id` is absent |
| `aspects` | `list[str] \| None` | ❌ No | `None` | Explicit aspect list; overrides whatever the domain config specifies |
| `method` | `AnalysisMethod` | ❌ No | `AnalysisMethod.llm` | Which analysis backend to use |

**Resolution priority:** `domain_id` → saved config aspects → `aspects` override → `domain` fallback label.

---

#### `AspectResult`

```python
class AspectResult(BaseModel):
    aspect: str
    sentiment: str  # positive | negative | not_mentioned
```

**What it does:** Represents the analysis result for a single aspect within one review.

| Field | Type | Description |
|-------|------|-------------|
| `aspect` | `str` | The aspect name (e.g., `"service"`) |
| `sentiment` | `str` | One of `"positive"`, `"negative"`, or `"not_mentioned"` |

**Note:** `sentiment` is typed as `str` rather than an `Enum`, allowing the backend flexibility in edge-case output while still documenting the expected contract in comments.

---

#### `AnalyzeResponse`

```python
class AnalyzeResponse(BaseModel):
    domain: str
    aspects: list[str]
    method: str
    results: list[AspectResult]
```

**What it does:** Response body returned by the single-review analysis endpoint.

| Field | Type | Description |
|-------|------|-------------|
| `domain` | `str` | The domain label that was used for analysis |
| `aspects` | `list[str]` | The full list of aspects that were evaluated |
| `method` | `str` | Human-readable string of the analysis method used |
| `results` | `list[AspectResult]` | One `AspectResult` per aspect |

---

### Batch Job Models

---

#### `JobSubmitResponse`

```python
class JobSubmitResponse(BaseModel):
    job_id: str
    status: JobStatus
    message: str
```

**What it does:** Immediate response returned when a batch job is accepted for processing.

| Field | Type | Description |
|-------|------|-------------|
| `job_id` | `str` | Unique identifier to poll for status |
| `status` | `JobStatus` | Always `JobStatus.queued` at submission time |
| `message` | `str` | Human-readable confirmation message |

---

#### `AspectBreakdown`

```python
class AspectBreakdown(BaseModel):
    aspect: str
    positive_pct: float
    negative_pct: float
    not_mentioned_pct: float
    total_mentioned: int
```

**What it does:** Aggregated sentiment statistics for one aspect across all reviews in a batch job.

| Field | Type | Description |
|-------|------|-------------|
| `aspect` | `str` | Aspect name |
| `positive_pct` | `float` | Percentage of reviews mentioning this aspect positively |
| `negative_pct` | `float` | Percentage of reviews mentioning this aspect negatively |
| `not_mentioned_pct` | `float` | Percentage of reviews that did not mention this aspect |
| `total_mentioned` | `int` | Count of reviews where the aspect was explicitly mentioned |

**Note:** Percentages are expected to be in the range `[0.0, 100.0]`. `positive_pct + negative_pct + not_mentioned_pct` should sum to `100.0`.

---

#### `PainPoint`

```python
class PainPoint(BaseModel):
    aspect: str
    negative_count: int
    example_quotes: list[str]
```

**What it does:** Highlights a specific aspect that received significant negative sentiment, with supporting evidence.

| Field | Type | Description |
|-------|------|-------------|
| `aspect` | `str` | The problematic aspect |
| `negative_count` | `int` | Total number of reviews that rated this aspect negatively |
| `example_quotes` | `list[str]` | Representative review excerpts showing the negative sentiment |

---

#### `Report`

```python
class Report(BaseModel):
    total_reviews: int
    domain: str
    aspects: list[str]
    breakdown: list[AspectBreakdown]
    pain_points: list[PainPoint]  # sorted worst-first
    llm_summary: str | None = None
```

**What it does:** Complete aggregated report produced at the end of a batch job.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `total_reviews` | `int` | ✅ Yes | Total number of reviews processed |
| `domain` | `str` | ✅ Yes | Domain used for the analysis |
| `aspects` | `list[str]` | ✅ Yes | Aspects that were analyzed |
| `breakdown` | `list[AspectBreakdown]` | ✅ Yes | Per-aspect statistical breakdown |
| `pain_points` | `list[PainPoint]` | ✅ Yes | Sorted worst-first list of problematic aspects |
| `llm_summary` | `str \| None` | ❌ No | Optional natural-language narrative summary generated by the LLM |

---

#### `ReviewPrediction`

```python
class ReviewPrediction(BaseModel):
    review_index: int
    review_snippet: str  # first 120 chars
    results: list[AspectResult]
```

**What it does:** Per-review prediction record stored as part of a job's detailed output.

| Field | Type | Description |
|-------|------|-------------|
| `review_index` | `int` | Zero-based position of this review in the input batch |
| `review_snippet` | `str` | First 120 characters of the review text (for display purposes) |
| `results` | `list[AspectResult]` | Aspect-level sentiment results for this review |

---

#### `JobStatusResponse`

```python
class JobStatusResponse(BaseModel):
    job_id: str
    status: JobStatus
    progress: str | None = None
    error: str | None = None
    predictions: list[ReviewPrediction] | None = None
    report: Report | None = None
    created_at: str
    completed_at: str | None = None
```

**What it does:** Full job status payload returned by the job polling endpoint. Field availability varies by `status`.

| Field | Type | Available when | Description |
|-------|------|----------------|-------------|
| `job_id` | `str` | Always | Unique job identifier |
| `status` | `JobStatus` | Always | Current job lifecycle state |
| `progress` | `str \| None` | `running` | Human-readable progress string, e.g. `"12/50 reviews"` |
| `error` | `str \| None` | `failed` | Error message if the job failed |
| `predictions` | `list[ReviewPrediction] \| None` | `done` | Full per-review results |
| `report` | `Report \| None` | `done` | Aggregated batch report |
| `created_at` | `str` | Always | ISO 8601 timestamp of job creation |
| `completed_at` | `str \| None` | `done` / `failed` | ISO 8601 timestamp of job completion |

---

### IMDB SSE Pipeline Models

---

#### `IMDBReportRequest`

```python
class IMDBReportRequest(BaseModel):
    imdb_url: str = Field(..., description="IMDB movie URL (must contain tt... ID)")
    aspects: list[str] | None = Field(
        None, description="Aspects to analyze (defaults to movie preset)"
    )
```

**What it does:** Request body for the IMDB review scraping and SSE (Server-Sent Events) analysis pipeline. Triggers a streaming pipeline that fetches reviews from an IMDB movie page and performs aspect-based sentiment analysis in real time.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `imdb_url` | `str` | ✅ Yes | Full IMDB movie URL; must contain a valid `tt`-prefixed title ID (e.g., `https://www.imdb.com/title/tt0111161/`) |
| `aspects` | `list[str] \| None` | ❌ No | Explicit aspects to evaluate; falls back to the built-in movie domain preset when `None` |

**Side effects / dependencies:**
- The backend is expected to extract the `tt...` ID from `imdb_url` for scraping; invalid URLs that lack this pattern should result in a validation or HTTP error at the route level.
- When `aspects` is `None`, the server resolves the movie preset domain's aspect list, meaning this field has an implicit dependency on the preset domain configuration.

---

## 3. What Changed

### Summary of the Diff

The diff adds the `IMDBReportRequest` model to the bottom of `api/models.py`, along with a section comment (`# ── IMDB Report (SSE pipeline) ──`).

### What Was Added

```python
# ── IMDB Report (SSE pipeline) ──────────────────────────────────────────────

class IMDBReportRequest(BaseModel):
    imdb_url: str = Field(..., description="IMDB movie URL (must contain tt... ID)")
    aspects: list[str] | None = Field(
        None, description="Aspects to analyze (defaults to movie preset)"
    )
```

### Functional Significance

| Dimension | Detail |
|-----------|--------|
| **New public API surface** | Introduces a new request schema (`IMDBReportRequest`) that API route handlers can now reference to validate and parse incoming requests for the IMDB SSE pipeline endpoint |
| **New capability unlocked** | Enables a dedicated pipeline for scraping IMDB movie reviews and streaming analysis results via Server-Sent Events — a real-time pattern distinct from the existing async batch job system |
| **Aspect defaulting behavior** | The `aspects: list[str] \| None = None` pattern means callers can omit aspects entirely, relying on the movie domain preset; this is user-facing behavior |
| **URL validation responsibility** | The `imdb_url` field is a plain `str` with no Pydantic `HttpUrl` or regex validator at the model level; the `tt...` ID extraction and validation is deferred to route or service logic |

### Behavioral Differences from Before

- **Before:** No model existed to handle IMDB-specific requests; any such endpoint would have lacked a validated request schema.
- **After:** The `IMDBReportRequest` model provides structured validation and documentation for the IMDB pipeline. API consumers now receive clear field descriptions and type enforcement.
- There are **no modifications or removals** of any previously existing models or enumerations; all prior behavior is fully preserved.

---

## 4. Dependencies & Integration

### What This Module Imports

| Import | Source | Purpose |
|--------|--------|---------|
| `annotations` | `
