# `app/report_generator.py` — Technical Documentation

---

## 1. Module Overview

`report_generator.py` implements a **Retrieval-Augmented Generation (RAG) pipeline** for producing structured, narrative reports from a corpus of textual reviews. It is the highest-level orchestration module in the application, sitting above the preprocessing, sentiment analysis, and configuration layers.

### Responsibilities

| Responsibility | Description |
|---|---|
| **Corpus construction** | Sentence-tokenizes and embeds all review text into a vector index |
| **Two-stage semantic retrieval** | For each aspect, retrieves candidate sentences via bi-encoder cosine similarity, then re-ranks with a cross-encoder for higher precision |
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

### 2.1 Module-Level State

```python
_reranker_model = None
```

A module-level singleton that holds the lazily loaded `CrossEncoder` instance used for re-ranking retrieved candidates. Initialized to `None` on import and populated on first use by `_get_reranker_model()`.

---

### 2.2 `_get_reranker_model` *(internal)*

```python
def _get_reranker_model() -> CrossEncoder:
```

**Description:**  
Lazy-loading accessor for the cross-encoder re-ranking model. Initializes the singleton from `CROSS_ENCODER_MODEL` (from config) on first call; returns the cached instance on subsequent calls. Follows the same pattern used for the sentence-transformer model in `sentiment_analyzer.py`.

**Returns:**  
`CrossEncoder` — a `sentence_transformers.CrossEncoder` instance loaded from the configured model name.

**Side Effects:**
- Mutates the module-level `_reranker_model` global on first call
- Triggers model download and loading from disk on first call (potentially slow)

---

### 2.3 `build_corpus`

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
- Encodes all sentences in a single batch call — efficient but memory usage scales with corpus size

---

### 2.4 `_retrieve_candidates` *(internal)*

```python
def _retrieve_candidates(aspect: str, corpus: dict, k: int = 30) -> list[dict]:
```

**Description:**  
The **first stage** of the two-stage retrieval pipeline. Encodes the aspect string as a query embedding and computes cosine similarity against every sentence in the corpus using the bi-encoder (sentence-transformer). Returns the top-`k` candidate sentences by cosine similarity score.

This function was previously the entirety of retrieval logic (under the name `retrieve_for_aspect`). It has been refactored into an internal helper to serve as the candidate generation step before cross-encoder re-ranking.

**Parameters:**

| Parameter | Type | Description |
|---|---|---|
| `aspect` | `str` | The aspect label to query (e.g., `"acting"`, `"plot"`) |
| `corpus` | `dict` | A corpus dict as returned by `build_corpus` |
| `k` | `int` | Maximum number of candidates to retrieve (default: `30`; capped to corpus size) |

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
- Uses `numpy.argsort` for ranking — O(n) in corpus sentence count

---

### 2.5 `_rerank_candidates` *(internal)*

```python
def _rerank_candidates(aspect: str, candidates: list[dict], k: int = 10) -> list[dict]:
```

**Description:**  
The **second stage** of the two-stage retrieval pipeline. Accepts a set of candidate sentences (as produced by `_retrieve_candidates`) and re-scores them using a cross-encoder model, which jointly encodes the aspect query and each candidate sentence for higher-precision relevance scoring. Returns the top-`k` candidates by cross-encoder score.

Cross-encoders are substantially more accurate than bi-encoders for relevance ranking but are too slow to run over an entire corpus — hence the two-stage design where bi-encoder retrieval narrows the field first.

**Parameters:**

| Parameter | Type | Description |
|---|---|---|
| `aspect` | `str` | The aspect label (used as the query in each cross-encoder pair) |
| `candidates` | `list[dict]` | Candidate sentences from `_retrieve_candidates`; each must have a `"sentence"` key |
| `k` | `int` | Number of top results to return after re-ranking (default: `10`) |

**Returns:**  
`list[dict]` — same shape as input dicts, but with `"score"` overwritten with the cross-encoder score (a `float`). Sorted by descending cross-encoder score. Returns an empty list if `candidates` is empty.

**Side Effects / Dependencies:**
- Calls `_get_reranker_model()` — triggers lazy load of `CrossEncoder` on first invocation
- Calls `model.predict()` on all candidate pairs in a single batch
- Handles the case where `model.predict()` returns a `np.ndarray` by converting to a plain Python list

---

### 2.6 `retrieve_for_aspect`

```python
def retrieve_for_aspect(
    aspect: str,
    corpus: dict,
    k: int = 10,
    k_retrieve: int = 30,
) -> list[dict]:
```

**Description:**  
The **public retrieval interface**. Orchestrates the two-stage retrieval pipeline: first calls `_retrieve_candidates` to gather `k_retrieve` bi-encoder candidates, then calls `_rerank_candidates` to re-score and return the top-`k` results by cross-encoder relevance.

This function's signature has changed in this commit: it previously performed only single-stage bi-encoder retrieval and accepted only `aspect`, `corpus`, and `k`. It now adds a `k_retrieve` parameter and internally delegates to the two-stage pipeline.

**Parameters:**

| Parameter | Type | Description |
|---|---|---|
| `aspect` | `str` | The aspect label to retrieve sentences for |
| `corpus` | `dict` | A corpus dict as returned by `build_corpus` |
| `k` | `int` | Final number of results to return after re-ranking (default: `10`) |
| `k_retrieve` | `int` | Number of candidates to retrieve in the first stage before re-ranking (default: `30`) |

**Returns:**  
`list[dict]` — top-`k` sentences sorted by descending cross-encoder relevance score. Each dict contains `sentence`, `review_idx`, and `score` (cross-encoder score).

**Side Effects / Dependencies:**
- Calls both `_retrieve_candidates` and `_rerank_candidates` internally
- Triggers lazy loading of both the sentence-transformer model and the cross-encoder model on first use

---

### 2.7 `_compute_distribution` *(internal)*

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
`dict` structured as:

```python
{
    "positive":      {"count": int, "pct": float},
    "negative":      {"count": int, "pct": float},
    "not_mentioned": {"count": int, "pct": float},
}
```

Percentages are rounded to one decimal place. Safe against empty input via a `total = max(sum, 1)` guard.

---

### 2.8 `generate_aspect_section`

```python
def generate_aspect_section(
    aspect: str,
    retrieved: list[dict],
    distribution: dict,
) -> str:
```

**Description:**  
Synchronously calls the OpenAI Chat Completions API to produce a 2–4 sentence narrative paragraph about a single aspect. The prompt is grounded with retrieved quote evidence and sentiment distribution statistics. The model is explicitly instructed not to invent details beyond the provided quotes.

**Parameters:**

| Parameter | Type | Description |
|---|---|---|
| `aspect` | `str` | The aspect being described (embedded in the prompt) |
| `retrieved` | `list[dict]` | Ranked sentences from `retrieve_for_aspect`, each with `review_idx` and `score` |
| `distribution` | `dict` | Sentiment distribution from `_compute_distribution` |

**Returns:**  
`str` — LLM-generated narrative text, stripped of leading/trailing whitespace.

**Side Effects / Dependencies:**
- Calls `_get_openai_client()` — synchronous OpenAI client singleton
- Makes a **blocking** HTTP API call
- Uses `OPENAI_MODEL` and `OPENAI_MAX_TOKENS` from config; temperature fixed at `0.3`

---

### 2.9 `generate_report`

```python
def generate_report(
    reviews: list[str],
    aspects: list[str] | None = None,
    method: str = "LLM (OpenAI)",
) -> dict:
```

**Description:**  
The synchronous end-to-end report generation entry point. Orchestrates four sequential steps:

1. **Sentiment analysis** — calls `analyze()` on each review serially
2. **Corpus building** — encodes all review sentences via `build_corpus()`
3. **Per-aspect processing** — for each aspect: collects sentiments, computes distribution, retrieves quotes via the two-stage pipeline, generates an LLM narrative
4. **Overall summary** — calls OpenAI to produce a 2–3 sentence cross-aspect summary

**Parameters:**

| Parameter | Type | Description |
|---|---|---|
| `reviews` | `list[str]` | Raw review texts to analyze |
| `aspects` | `list[str] \| None` | Aspects to analyze; falls back to `DEFAULT_ASPECTS` from config if `None` or empty |
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
- Makes `len(reviews) + len(aspects) + 1` OpenAI API calls (all serial/blocking)
- Encodes the full corpus once; computationally proportional to total sentence count
- Triggers lazy loading of both the sentence-transformer and cross-encoder models
- `method` is forwarded to `analyze()` and determines which sentiment backend is used

---

### 2.10 `async_generate_aspect_section`

```python
async def async_generate_aspect_section(
    aspect: str,
    retrieved: list[dict],
    distribution: dict,
) -> str:
```

**Description:**  
Async counterpart to `generate_aspect_section`. Functionally identical in prompt construction and output format, but uses the async OpenAI client and `await`s the API call, making it safe to run concurrently inside `asyncio.gather()`.

**Parameters:** Identical to `generate_aspect_section`.

**Returns:** `str` — LLM-generated narrative text, stripped of whitespace.

**Side Effects / Dependencies:**
- Calls `_get_async_openai_client()` — async OpenAI client singleton
- Awaitable; does not block the event loop during the API call

---

### 2.11 `async_generate_report`

```python
async def async_generate_report(
    reviews: list[str],
    aspects: list[str] | None = None,
    on_stage: callable = None,
) -> dict:
```

**Description:**  
The primary async entry point for report generation, designed for web server contexts (e.g., FastAPI with SSE streaming). Mirrors the four-step logic of `generate_report` with two key performance differences:

- **Sentiment analysis** is performed concurrently via `async_analyze_batch()`
- **Aspect narrative generation** fans out all aspects concurrently via `asyncio.gather()`

Progress events are emitted via the optional `on_stage` callback at each pipeline stage.

**Pipeline stages and callback events:**

| Stage string | Timing | `data` payload |
|---|---|---|
| `"analyzing"` | Before and after batch sentiment analysis | `{"progress": int, "total": int}` |
| `"generating"` | At corpus build, narrative generation, summary | `{"message": str}` |
| `"aspect_complete"` | After each aspect report is assembled | Full aspect report dict |

**Parameters:**

| Parameter | Type | Description |
|---|---|---|
| `reviews` | `list[str]` | Raw review texts to analyze |
| `aspects` | `list[str] \| None` | Aspects to analyze; falls back to `DEFAULT_ASPECTS` if `None` or empty |
| `on_stage` | `callable \| None` | Async callback `async (stage: str, data: dict) -> None`; no-op if `None` |

**Returns:**  
Identical structure to `generate_report` return value (see §2.9).

**Side Effects / Dependencies:**
