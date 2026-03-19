# `app/report_generator.py` — Technical Documentation

---

## 1. Module Overview

`report_generator.py` implements a **Retrieval-Augmented Generation (RAG) pipeline** for producing structured, narrative reports from a corpus of textual reviews. It is the highest-level orchestration module in the application, sitting above the preprocessing, sentiment analysis, and configuration layers.

### Responsibilities

| Responsibility | Description |
|---|---|
| **Corpus construction** | Sentence-tokenizes and embeds all review text into a vector index |
| **Semantic retrieval** | For each aspect of interest, retrieves the most relevant review sentences using cosine similarity |
| **Sentiment aggregation** | Collects per-aspect sentiment labels across all reviews and computes distribution statistics |
| **LLM narrative generation** | Calls an OpenAI chat model to write grounded, evidence-backed narrative sections per aspect |
| **Report assembly** | Combines per-aspect results and an overall summary into a structured report dictionary |
| **Markdown formatting** | Serializes the report dictionary into a human-readable Markdown document |

### Position in the System

```
[Input: list[str] reviews]
        │
        ▼
  preprocessing.py          ← clean_text, get_sentences
        │
        ▼
  sentiment_analyzer.py     ← analyze / async_analyze_batch, embeddings, OpenAI clients
        │
        ▼
  report_generator.py       ← RAG pipeline, LLM narration, report assembly  ◄── THIS MODULE
        │
        ▼
  [Output: report dict / Markdown string]
```

The module exposes both **synchronous** (`generate_report`) and **asynchronous** (`async_generate_report`) entry points to accommodate different runtime environments (e.g., a blocking script vs. a FastAPI/async web server with Server-Sent Events progress callbacks).

---

## 2. Key Components

### 2.1 `build_corpus`

```python
def build_corpus(reviews: list[str]) -> dict:
```

**Description:**  
Transforms a flat list of review strings into a searchable embedding corpus. Each review is cleaned, sentence-tokenized, and then all sentences are encoded into dense vectors using the shared sentence-transformer model.

**Parameters:**

| Parameter | Type | Description |
|---|---|---|
| `reviews` | `list[str]` | Raw review texts to index |

**Returns:**  
A `dict` with three keys:

| Key | Type | Description |
|---|---|---|
| `sentences` | `list[str]` | All sentences extracted from all reviews, in order |
| `review_indices` | `list[int]` | Parallel array mapping each sentence back to its source review (0-indexed) |
| `embeddings` | `np.ndarray` | Shape `(n_sentences, embedding_dim)` — dense float embeddings |

**Side Effects / Dependencies:**
- Calls `clean_text()` and `get_sentences()` from `preprocessing.py`
- Calls `_get_sentence_model()` from `sentiment_analyzer.py` (lazy-loaded, cached singleton)
- Encoding all sentences in one batch call is efficient but memory-proportional to corpus size

---

### 2.2 `retrieve_for_aspect`

```python
def retrieve_for_aspect(aspect: str, corpus: dict, k: int = 10) -> list[dict]:
```

**Description:**  
Encodes the aspect string as a query embedding and computes cosine similarity against every sentence in the corpus. Returns the top-`k` most semantically relevant sentences, sorted by descending relevance score.

**Parameters:**

| Parameter | Type | Description |
|---|---|---|
| `aspect` | `str` | The aspect label to query (e.g., `"acting"`, `"plot"`) |
| `corpus` | `dict` | A corpus dict as returned by `build_corpus` |
| `k` | `int` | Maximum number of results to return (default: `10`; capped to corpus size) |

**Returns:**  
`list[dict]` — each dict contains:

| Key | Type | Description |
|---|---|---|
| `sentence` | `str` | The retrieved sentence text |
| `review_idx` | `int` | 0-indexed source review number |
| `score` | `float` | Cosine similarity score in `[-1.0, 1.0]` |

**Side Effects / Dependencies:**
- Calls `_get_sentence_model()` to encode the aspect query
- Uses `sentence_transformers.util.cos_sim` for similarity computation
- Uses `numpy.argsort` for ranking — O(n) in corpus sentences

---

### 2.3 `_compute_distribution` *(internal)*

```python
def _compute_distribution(aspect_results: list[dict]) -> dict:
```

**Description:**  
Aggregates sentiment labels for a single aspect across all reviews into counts and percentages. Any label not in `{"positive", "negative", "not_mentioned"}` is bucketed into `"not_mentioned"`.

**Parameters:**

| Parameter | Type | Description |
|---|---|---|
| `aspect_results` | `list[dict]` | Records from sentiment analysis, each expected to have a `"sentiment"` key |

**Returns:**  
`dict` — structured as:
```python
{
    "positive":      {"count": int, "pct": float},
    "negative":      {"count": int, "pct": float},
    "not_mentioned": {"count": int, "pct": float},
}
```
Percentages are rounded to one decimal place. Safe against empty input (uses `total = 1` guard).

---

### 2.4 `generate_aspect_section`

```python
def generate_aspect_section(
    aspect: str,
    retrieved: list[dict],
    distribution: dict,
) -> str:
```

**Description:**  
Synchronously calls the OpenAI Chat Completions API to produce a 2–4 sentence narrative paragraph about a single aspect. The prompt is grounded with retrieved quote evidence and the sentiment distribution statistics. The model is instructed not to invent details beyond the provided quotes.

**Parameters:**

| Parameter | Type | Description |
|---|---|---|
| `aspect` | `str` | The aspect being described (used in the prompt) |
| `retrieved` | `list[dict]` | Ranked sentences from `retrieve_for_aspect` |
| `distribution` | `dict` | Sentiment distribution from `_compute_distribution` |

**Returns:**  
`str` — LLM-generated narrative text, stripped of leading/trailing whitespace.

**Side Effects / Dependencies:**
- Calls `_get_openai_client()` — synchronous OpenAI client
- Makes a **blocking** API call; uses `OPENAI_MODEL` and `OPENAI_MAX_TOKENS` from config
- Temperature fixed at `0.3` for reproducibility

---

### 2.5 `generate_report`

```python
def generate_report(
    reviews: list[str],
    aspects: list[str] | None = None,
    method: str = "LLM (OpenAI)",
) -> dict:
```

**Description:**  
The synchronous end-to-end report generation entry point. Orchestrates four sequential steps:

1. **Sentiment analysis** — calls `analyze()` on each review (one by one, blocking)
2. **Corpus building** — encodes all review sentences via `build_corpus()`
3. **Per-aspect processing** — for each aspect: collects sentiments, computes distribution, retrieves quotes, generates LLM narrative
4. **Overall summary** — calls OpenAI to produce a 2–3 sentence cross-aspect summary

**Parameters:**

| Parameter | Type | Description |
|---|---|---|
| `reviews` | `list[str]` | Raw review texts to analyze |
| `aspects` | `list[str] \| None` | Aspects to analyze; falls back to `DEFAULT_ASPECTS` from config |
| `method` | `str` | Sentiment analysis method passed to `analyze()` (default: `"LLM (OpenAI)"`) |

**Returns:**  
`dict` with the following structure:

```python
{
    "n_reviews": int,
    "aspects": [
        {
            "name": str,
            "distribution": {
                "positive":      {"count": int, "pct": float},
                "negative":      {"count": int, "pct": float},
                "not_mentioned": {"count": int, "pct": float},
            },
            "narrative": str,       # LLM-generated paragraph
            "top_quotes": [
                {"sentence": str, "review": int},  # review is 1-indexed
                # up to 5 entries
            ],
        },
        # one entry per aspect
    ],
    "overall_summary": str,         # LLM-generated cross-aspect summary
}
```

**Side Effects / Dependencies:**
- Makes `len(reviews) + len(aspects) + 1` OpenAI API calls (serial)
- Encodes the full corpus once per call; computationally proportional to total sentence count
- `method` parameter is forwarded to `analyze()` and determines which sentiment backend is used

---

### 2.6 `async_generate_aspect_section`

```python
async def async_generate_aspect_section(
    aspect: str,
    retrieved: list[dict],
    distribution: dict,
) -> str:
```

**Description:**  
Async counterpart to `generate_aspect_section`. Functionally identical in prompt construction and output, but uses the async OpenAI client so it can be awaited inside `asyncio.gather()` for concurrent execution.

**Parameters:** Identical to `generate_aspect_section`.

**Returns:** `str` — LLM-generated narrative text.

**Side Effects / Dependencies:**
- Calls `_get_async_openai_client()` — async OpenAI client singleton
- Awaits the OpenAI API call; safe to run concurrently with other aspect sections

---

### 2.7 `async_generate_report`

```python
async def async_generate_report(
    reviews: list[str],
    aspects: list[str] | None = None,
    on_stage: callable = None,
) -> dict:
```

**Description:**  
The primary async entry point for report generation, designed for web server contexts (e.g., FastAPI with SSE streaming). Mirrors the four-step logic of `generate_report` but with two key differences:

- **Sentiment analysis** is performed concurrently via `async_analyze_batch()`
- **Aspect narrative generation** runs all aspects concurrently via `asyncio.gather()`
- **Progress callbacks** are fired at each pipeline stage via `on_stage`

**Pipeline stages and callback events:**

| Stage string | Timing | `data` payload |
|---|---|---|
| `"analyzing"` | Before and after batch sentiment analysis | `{"progress": int, "total": int}` |
| `"generating"` | At corpus build, narrative generation, summary | `{"message": str}` |
| `"aspect_complete"` | After each aspect report is assembled | The full aspect report dict |

**Parameters:**

| Parameter | Type | Description |
|---|---|---|
| `reviews` | `list[str]` | Raw review texts to analyze |
| `aspects` | `list[str] \| None` | Aspects to analyze; falls back to `DEFAULT_ASPECTS` |
| `on_stage` | `callable \| None` | Async callback `async (stage: str, data: dict) -> None` for progress events |

**Returns:**  
Identical structure to `generate_report` return value (see §2.5).

**Side Effects / Dependencies:**
- Calls `async_analyze_batch()` with `domain="movie"` hardcoded
- `build_corpus()` is called synchronously on the event loop — acceptable for moderate corpus sizes; large corpora may benefit from `asyncio.to_thread()`
- `on_stage` is only invoked if not `None`; errors in the callback are not caught

> ⚠️ **Note:** The `_on_analysis_progress` inner callback stub within `async_generate_report` currently does nothing. Fine-grained per-review analysis progress is not propagated through the SSE channel during the async path.

---

### 2.8 `format_report_markdown`

```python
def format_report_markdown(report: dict) -> str:
```

**Description:**  
Pure serialization function. Converts a report dictionary (as returned by `generate_report` or `async_generate_report`) into a formatted Markdown string suitable for display, file export, or downstream rendering.

**Output structure:**

```markdown
# Review Analysis Report (N reviews)

## Overall Summary

<overall_summary text>

## <Aspect Name>

**Sentiment distribution:** X% positive · Y% negative · Z% not mentioned

<narrative paragraph>

**Top quotes:**

- _(review #N)_ "sentence text"
...
```

**Parameters:**

| Parameter | Type | Description |
|---|---|---|
| `report` | `dict` | A report dict as produced by `generate_report` or `async_generate_report` |

**Returns:**  
`str` — a complete Markdown document as a single string.

**Side Effects:** None. Pure function with no I/O or external calls.

---

## 3. What Changed

This module was **introduced as a new file** in this commit (no prior version existed). The entire diff represents the initial implementation. Key design decisions embedded in this first version include:

### Dual Sync/Async Architecture

Two parallel execution paths were implemented from the start:

- `generate_report` / `generate_aspect_section` — blocking, suitable for scripts and synchronous web frameworks
- `async_generate_report` / `async_generate_aspect_section` — non-blocking, suitable for `asyncio`-based servers

The async path introduces a materially different performance profile: aspect narrative generation is fanned out via `asyncio.gather()`, reducing total LLM latency from `O(n_aspects × latency_per_call)` to approximately `O(max_single_call_latency)`.

### RAG vs. Direct Summarization

The decision to build a sentence-level embedding index (`build_corpus`) and retrieve per-aspect evidence (`retrieve_for_aspect`) before calling the LLM represents a deliberate RAG approach. This grounds the narrative output in specific review sentences and prevents hallucination, compared to passing raw review text directly to the LLM.

### Progress Callback System

The `on_stage` parameter in `async_generate_report` establishes a structured event model for real-time progress reporting (e.g., SSE to a browser). The `"aspect_complete"` event fires incrementally as each aspect finishes, enabling streaming UI updates without waiting for the full report.

### Sentiment Analysis Integration

`generate_report` uses the synchronous `analyze()` function (one call per review, serial). `async_generate_report` uses `async_analyze_batch()` (all reviews concurrently). This means the async path has significantly lower total wall-clock time for large corpora, but the two paths are not otherwise behaviorally equivalent — the async path hardcodes `domain="movie"`, while the sync path accepts a `method` parameter.

### `domain="movie"` Hardcoding

In `async_generate_report`, the call to `async_analyze_batch` passes `domain="movie"` as a hardcoded literal. This is a notable limitation: the async path does not accept a `domain` parameter from callers, nor does it accept the `method` parameter that the sync path supports.

---

## 4. Dependencies & Integration

### Imports From

| Module | Symbols Used | Purpose |
|---|---|---|
| `app.config` | `DEFAULT_ASPECTS`, `OPENAI_MODEL`, `OPENAI_MAX_TOKENS`, `get_openai_api_key` | Model configuration, default aspect list |
| `app.preprocessing` | `clean_text`, `get_sentences` | Text normalization and sentence tokenization for corpus building |
| `app.sentiment_analyzer` | `_get_sentence_model`, `_get_openai_client`, `_get_async_openai_client`, `analyze`, `async_analyze_batch` | Embedding model singleton, OpenAI client singletons, per-review sentiment analysis |
| `sentence_transformers` | `util` | `cos_sim` for semantic similarity scoring |
| `numpy` | — | Embedding array operations, `argsort` for ranking |
| `asyncio` | — | `asyncio.gather` for concurrent async LLM calls |
| `pandas` | — | Imported but only used implicitly via `analyze()` return values (`.to_dict`) |

> **Note:** `pandas` and `get_openai_api_key` are imported but `get_openai_api_key` is not directly called in this module — API key retrieval is delegated to the client factory functions in
