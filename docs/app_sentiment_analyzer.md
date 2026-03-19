# `app/sentiment_analyzer.py` — Technical Documentation

---

## 1. Module Overview

`sentiment_analyzer.py` is the **core analytical engine** of the application. It is responsible for performing aspect-based sentiment analysis (ABSA) on free-text reviews using two distinct backends:

1. **LLM-based analysis** — delegates to the OpenAI Chat Completions API (GPT models) for high-accuracy, instruction-following sentiment classification.
2. **Zero-shot NLI-based analysis** — uses a locally hosted Hugging Face zero-shot classification pipeline (Natural Language Inference) for offline, cost-free inference.

Within the broader system architecture, this module sits between the **configuration/preprocessing layer** (`config.py`, `preprocessing.py`) and any **user-facing or orchestration layer** (e.g., a Streamlit UI, REST API, or batch processing script). It exposes both synchronous and asynchronous public interfaces, making it suitable for single-review interactive use as well as high-throughput concurrent batch workloads.

### Primary Responsibilities

| Responsibility | Mechanism |
|---|---|
| Aspect-based sentiment classification | NLI pipeline or OpenAI LLM |
| Sentence relevance ranking per aspect | Cosine similarity via SentenceTransformers |
| Lazy model/client initialization | Module-level singletons with guard checks |
| Concurrent batch processing | `asyncio` + `AsyncOpenAI` with semaphore control |
| Unified DataFrame output | `analyze()` entry point |
| Fault tolerance | Per-aspect error handling, fallback strategies |

---

## 2. Key Components

### 2.1 Module-Level Singletons

These private globals hold lazily initialized model and client instances. They are `None` at import time and are populated on first use by their respective loader functions.

```python
_sentence_model: SentenceTransformer | None = None
_zsc_pipeline: transformers.Pipeline | None = None
_openai_client: OpenAI | None = None
_async_openai_client: AsyncOpenAI | None = None
```

---

### 2.2 Private Loader Functions

These functions implement the **lazy-loading pattern**, ensuring expensive model downloads and API client instantiations only happen when actually needed.

---

#### `_get_sentence_model()`

```python
def _get_sentence_model() -> SentenceTransformer
```

**What it does:** Returns the shared `SentenceTransformer` model instance, initializing it from `SENTENCE_TRANSFORMER_MODEL` on first call.

**Side effects:** Populates `_sentence_model`; may trigger a model download on first use.

**Dependencies:** `SENTENCE_TRANSFORMER_MODEL` config constant.

---

#### `_get_zsc_pipeline()`

```python
def _get_zsc_pipeline() -> transformers.Pipeline
```

**What it does:** Returns the shared Hugging Face zero-shot classification pipeline, initialized with `ZERO_SHOT_MODEL` on CPU (`device=-1`).

**Side effects:** Populates `_zsc_pipeline`; may trigger a model download on first use.

**Dependencies:** `ZERO_SHOT_MODEL` config constant.

---

#### `_get_openai_client()`

```python
def _get_openai_client() -> OpenAI
```

**What it does:** Returns the shared synchronous `OpenAI` client, retrieving the API key via `get_openai_api_key()` on first call.

**Side effects:** Populates `_openai_client`.

**Dependencies:** `get_openai_api_key()` from `config`.

---

#### `_get_async_openai_client()`

```python
def _get_async_openai_client() -> AsyncOpenAI
```

**What it does:** Returns the shared `AsyncOpenAI` client for use in async coroutines. Created with the same API key retrieval mechanism as the synchronous client.

**Side effects:** Populates `_async_openai_client`.

**Dependencies:** `get_openai_api_key()` from `config`, `AsyncOpenAI` from `openai`.

> **Note:** This is a private helper but is architecturally significant as it backs all async public functions added in this release.

---

### 2.3 Public Utility Functions

---

#### `embed_sentences()`

```python
def embed_sentences(
    sentences: list,
    aspects: list
) -> tuple[torch.Tensor, torch.Tensor]
```

**What it does:** Encodes a list of sentences and a list of aspect names into dense vector embeddings using the shared `SentenceTransformer` model.

**Parameters:**

| Parameter | Type | Description |
|---|---|---|
| `sentences` | `list[str]` | Tokenized sentences from the review text |
| `aspects` | `list[str]` | Aspect labels to embed (e.g., `["acting", "plot"]`) |

**Returns:** A 2-tuple `(sent_emb, asp_emb)` where both are `torch.Tensor` objects on the device determined by the model.

**Dependencies:** `_get_sentence_model()`

---

#### `top_k_sentences_per_aspect()`

```python
def top_k_sentences_per_aspect(
    sentences: list,
    sent_emb: torch.Tensor,
    aspects: list,
    asp_emb: torch.Tensor,
    k: int = 3
) -> dict[str, list[str]]
```

**What it does:** For each aspect, computes cosine similarity between the aspect embedding and all sentence embeddings, then returns the top-`k` most relevant sentences. Automatically clamps `k` to the total number of available sentences to avoid index errors.

**Parameters:**

| Parameter | Type | Description |
|---|---|---|
| `sentences` | `list[str]` | The original sentence strings |
| `sent_emb` | `torch.Tensor` | Precomputed sentence embeddings |
| `aspects` | `list[str]` | Aspect labels |
| `asp_emb` | `torch.Tensor` | Precomputed aspect embeddings |
| `k` | `int` | Max sentences to return per aspect (default: `3`) |

**Returns:** `dict[str, list[str]]` — maps each aspect name to a list of up to `k` most relevant sentence strings.

**Edge cases:** If `k <= 0` or sentences is empty, returns an empty list for all aspects.

**Dependencies:** `torch.topk`, `sentence_transformers.util.cos_sim`

---

#### `concat_asp_sentences()`

```python
def concat_asp_sentences(
    top3: dict[str, list[str]]
) -> dict[str, str]
```

**What it does:** Joins the per-aspect sentence lists into single space-delimited strings, producing a focused text snippet per aspect suitable for NLI classification.

**Parameters:**

| Parameter | Type | Description |
|---|---|---|
| `top3` | `dict[str, list[str]]` | Output of `top_k_sentences_per_aspect()` |

**Returns:** `dict[str, str]` — maps each aspect to a concatenated string.

---

### 2.4 Public Analysis Functions

---

#### `nli_aspect_sentiment()`

```python
def nli_aspect_sentiment(
    review: str,
    aspects: list = None,
    threshold: float = None
) -> list[dict]
```

**What it does:** Performs aspect-based sentiment analysis entirely locally using a zero-shot NLI pipeline. For each aspect, it:

1. Cleans and tokenizes the review into sentences.
2. For reviews longer than 3 sentences, selects the top-3 most relevant sentences per aspect using semantic similarity.
3. Runs zero-shot classification with labels `["positive", "negative", "not_mentioned"]` using a hypothesis template: *"The sentiment towards `{aspect}` is `{label}`."*
4. Falls back to `"not_mentioned"` if the top score is below `threshold`.

**Parameters:**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `review` | `str` | — | Raw review text |
| `aspects` | `list[str]` | `DEFAULT_ASPECTS` | Aspects to evaluate |
| `threshold` | `float` | `DEFAULT_NLI_THRESHOLD` | Minimum confidence to accept a non-"not_mentioned" label |

**Returns:** `list[dict]` — each dict has keys:
- `"aspect"` (`str`)
- `"sentiment"` (`str`) — one of `"positive"`, `"negative"`, `"not_mentioned"`, or `"error"`
- `"confidence"` (`float`) — top classification score, rounded to 3 decimal places

**Error handling:**
- If preprocessing fails, falls back to using the full cleaned/raw review for all aspects.
- If NLI classification fails for a specific aspect, that aspect is recorded with `"error"` sentiment and `0.0` confidence.

**Dependencies:** `clean_text`, `get_sentences`, `embed_sentences`, `top_k_sentences_per_aspect`, `concat_asp_sentences`, `_get_zsc_pipeline`, config constants.

---

#### `llm_aspect_sentiment()`

```python
def llm_aspect_sentiment(
    review: str,
    aspects: list = None,
    max_tokens: int = None,
    domain: str = "product"
) -> list[dict]
```

**What it does:** Performs aspect-based sentiment analysis by sending the review to the OpenAI Chat Completions API with a structured prompt. The model is instructed to return a strict JSON array mapping aspects to sentiment labels.

**Parameters:**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `review` | `str` | — | Raw review text |
| `aspects` | `list[str]` | `DEFAULT_ASPECTS` | Aspects to classify |
| `max_tokens` | `int` | `OPENAI_MAX_TOKENS` | Maximum response tokens |
| `domain` | `str` | `"product"` | Domain context injected into the prompt (e.g., `"movie"`, `"restaurant"`) |

**Returns:** `list[dict]` — each dict has keys:
- `"aspect"` (`str`)
- `"sentiment"` (`str`) — one of `"positive"`, `"negative"`, `"not_mentioned"`

**JSON parsing strategy (two-stage):**
1. Direct `json.loads()` on the raw response.
2. If that fails: strips Markdown code fences (` ```json `) via regex, extracts the outermost `[...]` array, and retries.

**Raises:** `ValueError` with the partial response content if both parsing stages fail.

**API behaviour:** Called with `temperature=0` for deterministic output.

**Dependencies:** `_get_openai_client()`, `OPENAI_MODEL`, `OPENAI_MAX_TOKENS`, `DEFAULT_ASPECTS`.

---

#### `async_llm_aspect_sentiment()`  *(new in this release)*

```python
async def async_llm_aspect_sentiment(
    review: str,
    aspects: list = None,
    max_tokens: int = None,
    domain: str = "product"
) -> list[dict]
```

**What it does:** The `async`/`await` counterpart of `llm_aspect_sentiment()`. Functionally identical in prompt construction, JSON parsing logic, and return format, but uses `AsyncOpenAI` and `await`-based I/O to avoid blocking the event loop.

**Parameters:** Identical to `llm_aspect_sentiment()`.

**Returns:** Identical structure to `llm_aspect_sentiment()`.

**Raises:** `ValueError` on JSON parse failure, identical to the synchronous version.

**When to use:** Use this function when operating inside an `async` context (e.g., inside `async_analyze_batch()` or an async web framework handler). Do **not** call from synchronous code without wrapping in `asyncio.run()`.

**Dependencies:** `_get_async_openai_client()`, `OPENAI_MODEL`, `OPENAI_MAX_TOKENS`, `DEFAULT_ASPECTS`.

---

#### `async_analyze_batch()`  *(new in this release)*

```python
async def async_analyze_batch(
    reviews: list[str],
    aspects: list[str] = None,
    domain: str = "movie",
    max_concurrency: int = 10,
    on_progress: callable = None
) -> list[list[dict]]
```

**What it does:** Processes a list of reviews **concurrently** by dispatching each to `async_llm_aspect_sentiment()`. Concurrency is bounded via an `asyncio.Semaphore` to prevent overwhelming the OpenAI API with simultaneous requests.

**Parameters:**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `reviews` | `list[str]` | — | Collection of raw review texts |
| `aspects` | `list[str]` | `DEFAULT_ASPECTS` | Aspects to analyze across all reviews |
| `domain` | `str` | `"movie"` | Domain context for the LLM prompt |
| `max_concurrency` | `int` | `10` | Maximum number of simultaneous in-flight API calls |
| `on_progress` | `callable` | `None` | Optional callback invoked as `on_progress(completed: int, total: int)` after each review completes |

**Returns:** `list[list[dict]]` — a list of result sets in the **same order** as the input `reviews` list. Each inner list has the same structure as the return value of `async_llm_aspect_sentiment()`.

**Error handling:** If `async_llm_aspect_sentiment()` raises for a given review, that review's result defaults to `[{"aspect": a, "sentiment": "not_mentioned"} for a in aspects]` — i.e., silent failure with neutral values, preserving result index alignment.

**Ordering guarantee:** Results preserve input order regardless of completion order, because the internal `_analyze_one` coroutine writes to a pre-allocated `results` list by index.

**Side effects:** Calls `on_progress(completed, total)` after each review completes if the callback is provided; useful for driving progress bars.

**Dependencies:** `asyncio.Semaphore`, `asyncio.gather`, `async_llm_aspect_sentiment`, `DEFAULT_ASPECTS`.

---

#### `analyze()`

```python
def analyze(
    review: str,
    aspects: list = None,
    method: str = "LLM (OpenAI)",
    domain: str = "product"
) -> pd.DataFrame
```

**What it does:** The **primary synchronous entry point** for single-review analysis. Dispatches to either `llm_aspect_sentiment()` or `nli_aspect_sentiment()` based on `method`, normalizes the result into a DataFrame, and handles all errors gracefully by returning an error-row DataFrame instead of raising.

**Parameters:**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `review` | `str` | — | Raw review text |
| `aspects` | `list[str]` | `DEFAULT_ASPECTS` | Aspects to classify |
| `method` | `str` | `"LLM (OpenAI)"` | `"LLM (OpenAI)"` or `"Zero-shot NLI (local)"` |
| `domain` | `str` | `"product"` | Domain context (passed to LLM only) |

**Returns:** `pd.DataFrame` with columns:

| Column | Type | Description |
|---|---|---|
| `aspect` | `str` | The aspect label |
| `sentiment` | `str` | One of `"positive"`, `"negative"`, `"not_mentioned"` |

**Special cases:**

| Condition | Returned DataFrame |
|---|---|
| `review` is empty/falsy | Single row: `aspect=""`, `sentiment="(no review)"` |
| Any unhandled exception | Single row: `aspect="(error)"`, `sentiment="<ExceptionType>: <message>"` |

**Dependencies:** `llm_aspect_sentiment`, `nli_aspect_sentiment`, `pandas`.

---

## 3. What Changed

This commit introduces **first-class asynchronous support** for LLM-based sentiment analysis. The changes are entirely additive — no existing public functions were modified or removed.

### 3.1 New Imports

```diff
+import asyncio
-from openai import OpenAI
+from openai import OpenAI, AsyncOpenAI
```

- `asyncio` is now imported to support semaphore-based concurrency control.
- `AsyncOpenAI` is imported alongside the existing `OpenAI` client, providing the non-blocking HTTP client required for async corout
