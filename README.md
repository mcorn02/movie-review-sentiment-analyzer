# Product Reviewer - Aspect-Based Sentiment Analysis

A Python application for performing aspect-based sentiment analysis on movie reviews using two methods:
- **LLM (OpenAI)**: Uses GPT-4o-mini for sentiment classification
- **Zero-shot NLI (local)**: Uses `typeform/distilbert-base-uncased-mnli` running locally

## Installation

1. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set up your OpenAI API key (required for LLM method):
```bash
export OPENAI_API_KEY=your_api_key_here
```
Or create a `.env` file in the project root:
```
OPENAI_API_KEY=your_api_key_here
```

> **First run:** Models will be downloaded automatically (~100MB for sentence-transformers, ~500MB for the NLI model).

## Usage

### API Server

```bash
uvicorn api.main:app --reload
```

All API routes are served under the `/api` prefix (e.g. `/api/health`, `/api/report/imdb`).

In production, if a `frontend/dist` directory is present, the server will also serve the compiled frontend and handle client-side routing via an SPA fallback.

### Command-Line Interface

```bash
# Analyze a single review
python -m app.main --review "This movie had great acting but a weak plot."

# Analyze from a file
python -m app.main --file review.txt

# Use the local NLI method instead of OpenAI
python -m app.main --review "..." --method "Zero-shot NLI (local)"

# Custom aspects
python -m app.main --review "..." --aspects acting plot soundtrack

# Test with dataset (first N reviews)
python -m app.main --dataset-kaggle --test 5
python -m app.main --dataset path/to/IMDB_Dataset.csv --test 5
```

### CLI Options

| Flag | Description |
|------|-------------|
| `--review TEXT` | Review text to analyze |
| `--file PATH` | Path to file containing review text |
| `--dataset PATH` | Path to a local CSV dataset |
| `--dataset-kaggle` | Download IMDB dataset from Kaggle |
| `--aspects A B ...` | Custom aspects to analyze |
| `--method METHOD` | `"LLM (OpenAI)"` or `"Zero-shot NLI (local)"` |
| `--test N` | Analyze first N reviews from a dataset |

### IMDB Report Endpoint

`POST /api/report/imdb` accepts an IMDB movie URL, scrapes reviews, runs aspect-based sentiment analysis, and streams progress and results back as Server-Sent Events (SSE).

Stages emitted: `scraping` → `analyzing` → `generating` → `done`

**Request body:**
```json
{
  "imdb_url": "https://www.imdb.com/title/tt1375666/",
  "aspects": ["acting_performances", "story_plot"]
}
```

The `aspects` field is optional; omitting it uses the default aspects defined in `app/config.py`.

## Methods

| | LLM (OpenAI) | Zero-shot NLI (local) |
|--|--|--|
| **Accuracy** | Higher | Moderate |
| **Speed** | Fast (API) | Slower (local inference) |
| **Cost** | Per-request API cost | Free |
| **Privacy** | Review sent to OpenAI | Fully local |
| **Internet** | Required | Not required |

## Default Aspects

Defined in `app/config.py`:
- `acting_performances`
- `story_plot`
- `pacing`
- `visuals`
- `directing`
- `writing`

## Evaluation

Run inference on the gold dataset and evaluate:

```bash
# Generate predictions (saves to predictions.csv, checkpoints every 10 reviews)
python inference/run_inference_on_gold.py

# Compute macro F1 per aspect
python evaluation/final_sentiment_analysis.py
```

Gold dataset: `data/gold_dataset_aspect_level - gold_dataset_aspect_level.csv`

## Troubleshooting

**OpenAI API key not found:** Ensure `OPENAI_API_KEY` is set as an environment variable or in a `.env` file in the project root.

**Import errors:** Always run from the project root using `python -m app.main` — direct invocation (`python app/main.py`) breaks package imports.

**NLTK data missing:** Run `python -c "import nltk; nltk.download('punkt'); nltk.download('punkt_tab')"` manually.

**IMDB scraper returning 403:** IMDB may be rate-limiting requests. Wait a moment and try again.