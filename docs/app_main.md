# `app/main.py` — Module Documentation

## 1. Module Overview

`app/main.py` serves as the **primary entry point** for the `product_reviewer` application. It orchestrates all user-facing interaction modes — both a command-line interface (CLI) and a web server — and ties together the application's core subsystems: dataset loading, sentiment analysis, and report generation.

### Responsibilities

- **CLI argument parsing**: Exposes all configurable parameters (review source, aspects, analysis method, etc.) via `argparse`.
- **Dataset ingestion**: Supports loading IMDB-style CSV datasets either from a local file path or by downloading from Kaggle via `kagglehub`.
- **Single-review analysis**: Accepts review text directly (inline string or file), runs aspect-based sentiment analysis, and prints results to stdout.
- **Batch testing**: Iterates over the first *N* reviews of a loaded dataset and prints per-review results.
- **Web server launch**: Delegates HTTP API serving to a FastAPI/Uvicorn stack when `--web` is specified.

### Position in the System

```
User (CLI / shell)
        │
        ▼
  app/main.py          ← this module
  ├── app/config.py            (DEFAULT_ASPECTS constant)
  ├── app/sentiment_analyzer.py (analyze())
  ├── app/report_generator.py   (generate_report(), format_report_markdown())
  └── api/main.py              (FastAPI app, launched via uvicorn)
```

---

## 2. Key Components

### 2.1 Module-Level Imports & Optional Dependencies

```python
import kagglehub   # optional — set to None if not installed
```

`kagglehub` is wrapped in a `try/except ImportError` block so the module remains functional without it; Kaggle-download features are simply unavailable if the package is absent.

---

### 2.2 `load_dataset_kaggle`

```python
def load_dataset_kaggle(
    dataset_name: str = "lakshmi25npathi/imdb-dataset-of-50k-movie-reviews"
) -> pd.DataFrame | None
```

**Purpose**: Downloads a Kaggle dataset using `kagglehub` and loads the first discovered IMDB-named CSV file into a `pandas.DataFrame`.

| Parameter | Type | Description |
|-----------|------|-------------|
| `dataset_name` | `str` | Kaggle dataset slug in `owner/dataset-name` format. |

**Returns**: A `pd.DataFrame` on success, or `None` if:
- `kagglehub` is not installed.
- The download raises an exception.
- No CSV file whose name contains `'IMDB'` is found in the downloaded directory tree.

**Side Effects**:
- Prints progress messages to stdout.
- Triggers a network download to the local `kagglehub` cache directory.
- Walks the downloaded directory tree with `os.walk`.

**Dependencies**: `kagglehub`, `os`, `pandas`

---

### 2.3 `load_dataset_manual`

```python
def load_dataset_manual(file_path: str) -> pd.DataFrame | None
```

**Purpose**: Loads a local CSV file into a `pandas.DataFrame`.

| Parameter | Type | Description |
|-----------|------|-------------|
| `file_path` | `str` | Absolute or relative path to a CSV file. |

**Returns**: A `pd.DataFrame` on success, or `None` if:
- The file does not exist.
- Reading the file raises an exception.

**Side Effects**:
- Prints progress or error messages to stdout.
- Reads from the filesystem.

**Dependencies**: `os`, `pandas`

---

### 2.4 `analyze_review_cli`

```python
def analyze_review_cli(review: str, aspects: list, method: str) -> None
```

**Purpose**: Runs aspect-based sentiment analysis on a single review text and pretty-prints the results table to stdout.

| Parameter | Type | Description |
|-----------|------|-------------|
| `review` | `str` | The full text of the review to analyze. |
| `aspects` | `list` | List of aspect strings to evaluate (e.g., `["acting", "plot"]`). |
| `method` | `str` | Analysis backend — `"LLM (OpenAI)"` or `"Zero-shot NLI (local)"`. |

**Returns**: `None`

**Side Effects**:
- Prints a formatted header, the review text, a separator line, and a results table to stdout.
- Delegates to `app.sentiment_analyzer.analyze()`, which may make external API calls (OpenAI) or load an NLI model depending on `method`.

**Output format** (stdout):
```
Analyzing review using <method>...
Aspects: <aspect1>, <aspect2>, ...

Review:
<review text>

--------------------------------------------------------------------------------

Results:
<DataFrame table>
```

**Dependencies**: `app.sentiment_analyzer.analyze`

---

### 2.5 `main`

```python
def main() -> None
```

**Purpose**: Root entry point. Parses CLI arguments and dispatches to the appropriate execution mode (web server, single-review analysis, or batch testing).

**Returns**: `None`  
**Raises**: Calls `sys.exit(1)` on unrecoverable errors (missing file, failed dataset load when required, etc.).

#### Argument Reference

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--web` | flag | `False` | Launch the FastAPI web server via Uvicorn. |
| `--port` | `int` | `8000` | TCP port for the web server. |
| `--review` | `str` | `None` | Inline review text to analyze. |
| `--file` | `str` | `None` | Path to a plain-text file containing the review. |
| `--dataset` | `str` | `None` | Path to a local IMDB CSV dataset. |
| `--dataset-kaggle` | flag | `False` | Download the IMDB dataset from Kaggle. |
| `--aspects` | `str...` | `DEFAULT_ASPECTS` | One or more aspect labels to analyze. |
| `--method` | `str` | `"LLM (OpenAI)"` | Analysis method: `"LLM (OpenAI)"` or `"Zero-shot NLI (local)"`. |
| `--test` | `int` | `None` | Run analysis on the first N reviews of the loaded dataset. |

#### Execution Modes (priority order)

1. **Web server** (`--web`): Imports and starts `uvicorn`, pointing at `api.main:app`. Exits after server shuts down.
2. **Batch test** (`--test N`): Requires `--dataset` or `--dataset-kaggle`. Iterates over the first N rows of the `'review'` column.
3. **Single review** (`--review`, `--file`, or first row of loaded dataset): Calls `analyze_review_cli` once.
4. **No input**: Prints argparse help text and usage examples, then returns.

**Side Effects**:
- Prints to stdout throughout.
- May call `sys.exit(1)` on errors.
- Imports `uvicorn` lazily (only in web mode).

**Dependencies**: `argparse`, `sys`, `uvicorn` (optional/lazy), `app.config.DEFAULT_ASPECTS`, `load_dataset_kaggle`, `load_dataset_manual`, `analyze_review_cli`

---

## 3. What Changed

### 3.1 Removed: Gradio Interface

**Before**: The module included a `try/except` import of `gradio as gr` and a full `create_gradio_interface()` function that built a `gr.Blocks` UI with a text input, checkbox group for aspects, a radio selector for method, an "Analyze" button, and a results dataframe. The `--web` flag launched this Gradio interface via `demo.launch(share=False)`.

**After**: All Gradio-related code has been completely removed:
- The `import gradio as gr` guard block is gone.
- `create_gradio_interface()` no longer exists.
- The `--web` flag no longer references Gradio at all.

**Functional impact**: Users who previously relied on the Gradio UI (browser-based, self-contained) will find it no longer available. The `pip install gradio` requirement is dropped.

---

### 3.2 Added: FastAPI/Uvicorn Web Server

**Before**: `--web` launched a Gradio UI.

**After**: `--web` starts a **Uvicorn** server hosting the FastAPI application defined in `api/main.py`:

```python
import uvicorn
uvicorn.run("api.main:app", host="0.0.0.0", port=args.port, reload=True)
```

A new `--port` argument (default `8000`) controls which TCP port is used. The server starts with `reload=True`, enabling hot-reload during development.

**Functional impact**:
- The web interface is now an HTTP REST API (with auto-generated docs at `/docs`) rather than an interactive Gradio page.
- The server listens on all network interfaces (`0.0.0.0`) rather than loopback only.
- Users interacting via browser must use API clients or the Swagger UI instead of a form-based UI.
- A new dependency on `uvicorn` (and `fastapi` via `api/main.py`) is introduced.

---

### 3.3 Added: `report_generator` Import

```python
from .report_generator import generate_report, format_report_markdown
```

`generate_report` and `format_report_markdown` are now imported from `app.report_generator`. Note that while imported, neither function is called directly within the current body of `main.py` — they are available for future use or are used indirectly through the web API path.

---

### 3.4 Updated: CLI Example Strings

The help/example output strings were updated from:

```
python main.py --web
python main.py --review '...'
python main.py --dataset-kaggle --test 5
```

to:

```
python -m app.main --web
python -m app.main --review '...'
python -m app.main --dataset-kaggle --test 5
```

**Functional impact**: The examples now reflect the correct module invocation style (`python -m app.main`), which is consistent with how the package is structured. This is a user-visible documentation improvement.

---

### 3.5 Cosmetic: Whitespace Normalization

Trailing spaces after `"""` docstring content and within function bodies were removed (e.g., blank lines with trailing whitespace replaced by truly empty lines). No behavioral change.

---

## 4. Dependencies & Integration

### 4.1 Standard Library

| Module | Usage |
|--------|-------|
| `argparse` | CLI argument definition and parsing |
| `os` | File existence checks, directory walking |
| `sys` | `sys.exit()` on fatal errors |

### 4.2 Third-Party (Required)

| Package | Usage |
|---------|-------|
| `pandas` | DataFrame loading from CSV, result display |

### 4.3 Third-Party (Optional / Lazy)

| Package | Condition | Usage |
|---------|-----------|-------|
| `kagglehub` | Gracefully absent if not installed | Kaggle dataset download |
| `uvicorn` | Imported only when `--web` is passed | ASGI server for FastAPI app |

### 4.4 Internal Imports

| Module | Symbols Imported | Role |
|--------|-----------------|------|
| `app.config` | `DEFAULT_ASPECTS` | Default list of sentiment aspects |
| `app.sentiment_analyzer` | `analyze` | Core sentiment analysis logic |
| `app.report_generator` | `generate_report`, `format_report_markdown` | Report generation utilities |

### 4.5 Downstream / What Depends on This Module

| Consumer | How It Uses `main.py` |
|----------|-----------------------|
| `__main__` block | `if __name__ == "__main__": main()` — direct script execution |
| Package `__main__.py` (if present) | `python -m app` entry point |
| Shell / CI scripts | Invoked as `python -m app.main [args]` |
| `api/main.py` | Referenced indirectly — `main.py` launches it via Uvicorn but does not import from it |

---

`FUNCTIONAL_CHANGE: YES`
