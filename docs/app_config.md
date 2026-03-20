# `app/config.py` — Module Documentation

---

## 1. Module Overview

**File:** `app/config.py`
**Docstring:** *Configuration management and API key loading.*

`config.py` serves as the **centralized configuration hub** for the application. It is responsible for:

- **Loading environment variables** from a `.env` file at startup (via `python-dotenv`).
- **Defining application-wide constants** for model selection, thresholds, and default analytical parameters.
- **Providing secure access** to sensitive credentials (e.g., the OpenAI API key) through a guarded accessor function that fails fast with a clear error message if the key is absent.

Within the system architecture, this module sits at the **foundation layer** — it has no dependencies on other internal application modules and is expected to be imported by any component that requires configuration values, model identifiers, or API credentials. Because it calls `load_dotenv()` at import time, importing this module is a side-effectful operation and should occur early in the application lifecycle.

---

## 2. Key Components

### Constants

---

#### `DEFAULT_ASPECTS`

```python
DEFAULT_ASPECTS: list[str] = [
    "acting_performances",
    "story_plot",
    "pacing",
    "visuals",
    "directing",
    "writing"
]
```

**Description:**
A list of default aspect categories used during sentiment analysis. These represent the facets of a subject (e.g., a film or media piece) that the application analyzes by default when no custom aspects are provided by the caller.

| Attribute | Value |
|---|---|
| Type | `list[str]` |
| Default Count | 6 aspects |
| Usage Context | Sentiment/aspect-based analysis pipelines |

**Aspects defined:**
- `acting_performances` — Quality and believability of performances
- `story_plot` — Narrative structure and coherence
- `pacing` — Rhythm and flow of the content
- `visuals` — Cinematography, visual effects, or aesthetics
- `directing` — Directorial choices and execution
- `writing` — Script quality, dialogue, and storytelling craft

---

#### `DEFAULT_NLI_THRESHOLD`

```python
DEFAULT_NLI_THRESHOLD: float = 0.55
```

**Description:**
The default confidence threshold for **Natural Language Inference (NLI)**-based classification decisions. Predictions with a confidence score below this threshold may be discarded or treated as inconclusive.

| Attribute | Value |
|---|---|
| Type | `float` |
| Range | `0.0` – `1.0` |
| Default | `0.55` |

---

#### `DEFAULT_ZSC_THRESHOLD`

```python
DEFAULT_ZSC_THRESHOLD: float = 0.6
```

**Description:**
The default confidence threshold for **Zero-Shot Classification (ZSC)** decisions. Operates similarly to `DEFAULT_NLI_THRESHOLD` but applies specifically to the zero-shot classification pipeline.

| Attribute | Value |
|---|---|
| Type | `float` |
| Range | `0.0` – `1.0` |
| Default | `0.60` |

> **Note:** `DEFAULT_ZSC_THRESHOLD` is intentionally set slightly higher than `DEFAULT_NLI_THRESHOLD`, reflecting the expectation that zero-shot predictions should meet a stricter confidence bar before being acted upon.

---

#### `SENTENCE_TRANSFORMER_MODEL`

```python
SENTENCE_TRANSFORMER_MODEL: str = "all-MiniLM-L6-v2"
```

**Description:**
Identifier for the **Sentence Transformer** model used to generate dense vector embeddings for semantic similarity tasks.

| Attribute | Value |
|---|---|
| Type | `str` |
| Model Source | [Hugging Face — `sentence-transformers/all-MiniLM-L6-v2`](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2) |
| Characteristics | Lightweight, fast, 384-dimensional embeddings |

---

#### `CROSS_ENCODER_MODEL`

```python
CROSS_ENCODER_MODEL: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
```

**Description:**
Identifier for the **Cross-Encoder** model used for re-ranking or more precise relevance scoring between text pairs. Unlike bi-encoders (such as `SENTENCE_TRANSFORMER_MODEL`), a cross-encoder jointly processes both input texts together, producing a single relevance score rather than independent embeddings. This makes it more accurate for ranking tasks at the cost of higher inference latency.

| Attribute | Value |
|---|---|
| Type | `str` |
| Model Source | [Hugging Face — `cross-encoder/ms-marco-MiniLM-L-6-v2`](https://huggingface.co/cross-encoder/ms-marco-MiniLM-L-6-v2) |
| Characteristics | Trained on MS MARCO passage ranking dataset; optimized for relevance scoring between query-document pairs |
| Typical Usage | Re-ranking candidate passages retrieved by a bi-encoder in a retrieval pipeline |

> **Architectural note:** In a typical two-stage retrieval system, `SENTENCE_TRANSFORMER_MODEL` (bi-encoder) performs fast approximate candidate retrieval, and `CROSS_ENCODER_MODEL` then re-ranks those candidates with higher precision. The two constants are designed to work in tandem.

---

#### `ZERO_SHOT_MODEL`

```python
ZERO_SHOT_MODEL: str = "typeform/distilbert-base-uncased-mnli"
```

**Description:**
Identifier for the **zero-shot classification** model used to classify text into arbitrary label categories without task-specific training data.

| Attribute | Value |
|---|---|
| Type | `str` |
| Model Source | [Hugging Face — `typeform/distilbert-base-uncased-mnli`](https://huggingface.co/typeform/distilbert-base-uncased-mnli) |
| Characteristics | DistilBERT-based, trained on MNLI, efficient inference |

---

#### `OPENAI_MODEL`

```python
OPENAI_MODEL: str = "gpt-4o-mini"
```

**Description:**
The OpenAI model identifier used for all calls to the OpenAI API. Centralizing this value ensures that switching model versions requires a change in only one location.

| Attribute | Value |
|---|---|
| Type | `str` |
| Default Model | `gpt-4o-mini` |

---

#### `OPENAI_MAX_TOKENS`

```python
OPENAI_MAX_TOKENS: int = 350
```

**Description:**
The maximum number of tokens the OpenAI model is permitted to generate in a single API response. This acts as a cost-control and latency-management guardrail.

| Attribute | Value |
|---|---|
| Type | `int` |
| Default | `350` tokens |

---

### Functions

---

#### `get_openai_api_key`

```python
def get_openai_api_key() -> str:
```

**Description:**
Retrieves the OpenAI API key from the runtime environment. Reads the `OPENAI_API_KEY` environment variable, which may have been populated either by the shell environment or by the `.env` file loaded at module import time.

**Parameters:**
None.

**Returns:**

| Type | Description |
|---|---|
| `str` | The OpenAI API key string if present and non-empty |

**Raises:**

| Exception | Condition |
|---|---|
| `ValueError` | Raised when `OPENAI_API_KEY` is not set or resolves to an empty/falsy string |

**Error message on failure:**
```
OpenAI API key not found. Please set OPENAI_API_KEY environment variable
or add it to a .env file in the project root.
```

**Side Effects:**
- Reads from the process environment via `os.getenv()`.
- No writes or mutations occur.

**Usage Example:**
```python
from app.config import get_openai_api_key

try:
    api_key = get_openai_api_key()
    # Use api_key to initialize OpenAI client
except ValueError as e:
    print(f"Configuration error: {e}")
```

**Design Notes:**
- The function uses a **fail-fast** pattern — it raises immediately rather than returning `None` or a sentinel value, making misconfiguration obvious at the point of access rather than producing a cryptic downstream error.
- Calling this function at module load time in dependent modules is acceptable; it will only fail if the key is genuinely absent.

---

### Module-Level Side Effects

#### `load_dotenv()` (called at import time)

```python
load_dotenv()
```

This call executes **when the module is first imported**. It searches for a `.env` file starting from the current working directory and traverses upward, loading any found key-value pairs into `os.environ`. If no `.env` file is found, the call is a no-op — it does not raise an error.

**Implication:** Any module that imports from `app.config` will trigger environment variable loading as a side effect, which is generally desirable and expected for applications using `python-dotenv`.

---

## 3. What Changed

The diff introduces a single addition to the module: a new model identifier constant, `CROSS_ENCODER_MODEL`.

### What Was Added

```diff
+CROSS_ENCODER_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"
```

A new module-level string constant was inserted into the model configuration block, between `SENTENCE_TRANSFORMER_MODEL` and `ZERO_SHOT_MODEL`.

### What It Means Functionally

`CROSS_ENCODER_MODEL` exposes the Hugging Face model identifier `"cross-encoder/ms-marco-MiniLM-L-6-v2"` as a centrally managed configuration constant. Any module in the application that performs cross-encoder-based re-ranking or relevance scoring can now import this value from `app.config` rather than hardcoding the model string inline.

This follows the same pattern already established by `SENTENCE_TRANSFORMER_MODEL` and `ZERO_SHOT_MODEL` — all model identifiers are declared here so that changes to model versions require edits in exactly one place.

### Why the Change Matters Functionally

- **New capability signaled:** The addition of a cross-encoder constant indicates that the application now includes (or is being extended to include) a re-ranking stage in its retrieval or scoring pipeline. Cross-encoders complement bi-encoders by providing higher-accuracy pairwise scoring after an initial candidate retrieval step.
- **Centralized control:** Consumer modules can now reference `CROSS_ENCODER_MODEL` instead of embedding the model name as a magic string, making future model swaps (e.g., upgrading to a larger cross-encoder variant) a single-line change in `config.py`.
- **Discoverability:** The constant is immediately visible to any developer reading `config.py` as the authoritative list of models in use, improving maintainability and auditability of model dependencies.

### Behavioral Differences From Before

| Aspect | Before | After |
|---|---|---|
| `CROSS_ENCODER_MODEL` constant | Not present | Available as `app.config.CROSS_ENCODER_MODEL` |
| Cross-encoder model identifier | No centralized value | `"cross-encoder/ms-marco-MiniLM-L-6-v2"` |
| Runtime behavior (existing code) | Unchanged | Unchanged |
| Public API surface | Unchanged | Extended with one new exported name |
| Other constants and functions | Unchanged | Unchanged |

> **Important:** This change **extends** the module's public API by adding a new importable name. No existing constants, thresholds, or functions were modified or removed, so all previously written consumer code continues to work without alteration.

---

## 4. Dependencies & Integration

### External Dependencies

| Import | Package | Purpose |
|---|---|---|
| `os` | Python standard library | Access to environment variables via `os.getenv()` |
| `load_dotenv` | `python-dotenv` | Loads `.env` file contents into `os.environ` at import time |

### Internal Dependencies

None. `app/config.py` does **not** import from any other internal application module, making it a true leaf-level dependency in the project's import graph.

### What Depends On This Module

Any application component that requires:
- **Model identifiers** (`SENTENCE_TRANSFORMER_MODEL`, `CROSS_ENCODER_MODEL`, `ZERO_SHOT_MODEL`, `OPENAI_MODEL`, `OPENAI_MAX_TOKENS`) — typically ML pipeline modules and inference engines.
- **Classification thresholds** (`DEFAULT_NLI_THRESHOLD`, `DEFAULT_ZSC_THRESHOLD`) — analysis and post-processing modules.
- **Default analytical parameters** (`DEFAULT_ASPECTS`) — modules that orchestrate sentiment/aspect analysis.
- **API credentials** (`get_openai_api_key()`) — any module making OpenAI API calls.

**Expected consumers** within the project would include:
- Sentence embedding and semantic search modules (consuming `SENTENCE_TRANSFORMER_MODEL`)
- Re-ranking and relevance scoring modules (consuming `CROSS_ENCODER_MODEL`)
- Zero-shot classification wrappers (consuming `ZERO_SHOT_MODEL`, `DEFAULT_ZSC_THRESHOLD`)
- NLI-based classification modules (consuming `DEFAULT_NLI_THRESHOLD`)
- Sentiment and aspect analysis orchestrators (consuming `DEFAULT_ASPECTS`)
- OpenAI client initialization code (consuming `OPENAI_MODEL`, `OPENAI_MAX_TOKENS`, `get_openai_api_key()`)
- Application entry points and CLI handlers

### Environment Variables

| Variable | Required | Description |
|---|---|---|
| `OPENAI_API_KEY` | **Yes** (at call time of `get_openai_api_key()`) | OpenAI API authentication key |

**Resolution order for `OPENAI_API_KEY`:**
1. Shell/OS environment variable (set before process start)
2. `.env` file in the project root (loaded by `load_dotenv()` at import time)

---

`FUNCTIONAL_CHANGE: YES`
