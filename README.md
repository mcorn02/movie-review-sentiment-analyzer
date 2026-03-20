# Product Reviewer - Aspect-Based Sentiment Analysis

A web application that scrapes IMDB reviews for any movie and generates a structured sentiment report broken down by aspect (acting, plot, pacing, etc.), powered by two analysis methods:

- **LLM (OpenAI)**: GPT-4o-mini via API — higher accuracy, costs money
- **Zero-shot NLI (local)**: `typeform/distilbert-base-uncased-mnli` — free, offline, privacy-preserving

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

3. Install Playwright's Chromium browser (used for scraping IMDB reviews):
```bash
playwright install chromium
```

4. Install frontend dependencies and build:
```bash
cd frontend && npm install && npm run build
```

5. Set up your OpenAI API key (required for LLM method):
```bash
export OPENAI_API_KEY=your_api_key_here
```
Or create a `.env` file in the project root:
```
OPENAI_API_KEY=your_api_key_here
```

> **First run:** Models will be downloaded automatically (~500MB for sentence-transformers, ~1.6GB for the NLI model).

## Usage

### Web App (main workflow)

```bash
python -m app.main --web
```

This starts FastAPI on port 8000 and serves the React frontend. Open `http://localhost:8000` in your browser, paste an IMDB movie URL, and click **Generate Report**.

**What the report contains:**
- Per-aspect sentiment breakdown (positive / negative / not mentioned) across all scraped reviews
- Bar, pie, and radar charts visualizing sentiment distribution
- A RAG-generated narrative per aspect — grounded in direct quotes retrieved from the reviews
- An overall summary synthesizing sentiment across all aspects

**Frontend dev server** (with hot reload, proxies `/api` to port 8000):
```bash
cd frontend && npm run dev
```

### IMDB Report API

`POST /api/report/imdb` accepts an IMDB movie URL and streams progress + results as Server-Sent Events (SSE).

Stages: `scraping` → `analyzing` → `generating` → `done`

**Request body:**
```json
{
  "imdb_url": "https://www.imdb.com/title/tt1375666/",
  "aspects": ["acting_performances", "story_plot"]
}
```

The `aspects` field is optional; omitting it uses the default aspects defined in `app/config.py`.

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
| `--web` | Start the web server |
| `--review TEXT` | Review text to analyze |
| `--file PATH` | Path to file containing review text |
| `--dataset PATH` | Path to a local CSV dataset |
| `--dataset-kaggle` | Download IMDB dataset from Kaggle |
| `--aspects A B ...` | Custom aspects to analyze |
| `--method METHOD` | `"LLM (OpenAI)"` or `"Zero-shot NLI (local)"` |
| `--test N` | Analyze first N reviews from a dataset |

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

## Troubleshooting

**OpenAI API key not found:** Ensure `OPENAI_API_KEY` is set as an environment variable or in a `.env` file in the project root.

**Import errors:** Always run from the project root using `python -m app.main` — direct invocation (`python app/main.py`) breaks package imports.

**NLTK data missing:** Run `python -c "import nltk; nltk.download('punkt'); nltk.download('punkt_tab')"` manually.

**IMDB scraper blocked or returning no results:** The scraper uses Playwright with headless Chromium to bypass bot detection. If reviews fail to load, ensure Playwright's Chromium browser is installed (`playwright install chromium`) and try again.