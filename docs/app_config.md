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

The diff introduces a single line addition to the module:

```diff
+# fmt: skip
```

This comment is inserted immediately after the module docstring and before the `import os` statement.

### What Was Added

A `# fmt: skip` directive comment was added at the top of the import block.

### What It Means Functionally

`# fmt: skip` is a **Black formatter directive**. When the [Black](https://github.com/psf/black) code formatter processes a Python file, this comment instructs it to **skip reformatting the line(s) it is associated with**. In practice, when placed at the top of an import section or block, it can be used to preserve a manually ordered or intentionally structured sequence of imports that Black would otherwise reorder or reformat.

### Why the Change Matters

- **No runtime behavior is affected.** Python's interpreter ignores this as a standard comment — it has zero effect on execution, imports, or any logic in the module.
- **Formatter behavior is affected.** The `# fmt: skip` directive signals to Black that the developer intends for this code to remain in its current form and should not be automatically reformatted. This is relevant in CI pipelines where Black is run as a linter/formatter check.
- **Preservation of import ordering intent:** The placement before the `import os` line suggests the developer wants to maintain the specific import ordering as-is (e.g., preserving `import os` before `from dotenv import load_dotenv` without Black potentially grouping or reordering them differently).

### Behavioral Differences From Before

| Aspect | Before | After |
|---|---|---|
| Runtime execution | Identical | Identical |
| Black formatting | Block eligible for auto-formatting | Block exempt from Black reformatting |
| Import behavior | Unchanged | Unchanged |
| Public API | Unchanged | Unchanged |

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
- **Model identifiers** (`SENTENCE_TRANSFORMER_MODEL`, `ZERO_SHOT_MODEL`, `OPENAI_MODEL`, `OPENAI_MAX_TOKENS`) — typically ML pipeline modules and inference engines.
- **Classification thresholds** (`DEFAULT_NLI_THRESHOLD`, `DEFAULT_ZSC_THRESHOLD`) — analysis and post-processing modules.
- **Default analytical parameters** (`DEFAULT_ASPECTS`) — modules that orchestrate sentiment/aspect analysis.
- **API credentials** (`get_openai_api_key()`) — any module making OpenAI API calls.

**Expected consumers** within the project would include:
- Sentiment analysis pipeline modules
- Zero-shot classification wrappers
- OpenAI client initialization code
- Application entry points and CLI handlers

### Environment Variables

| Variable | Required | Description |
|---|---|---|
| `OPENAI_API_KEY` | **Yes** (at call time of `get_openai_api_key()`) | OpenAI API authentication key |

**Resolution order for `OPENAI_API_KEY`:**
1. Shell/OS environment variable (set before process start)
2. `.env` file in the project root (loaded by `load_dotenv()` at import time)

---

`FUNCTIONAL_CHANGE: NO`
