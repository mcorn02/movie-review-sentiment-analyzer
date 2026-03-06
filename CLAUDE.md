# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Aspect-based sentiment analysis tool for movie reviews. Supports two analysis methods:
- **LLM (OpenAI)**: GPT-4o-mini via API — higher accuracy, costs money
- **Zero-shot NLI (local)**: `typeform/distilbert-base-uncased-mnli` — free, offline, privacy-preserving

## Setup

```bash
pip install -r requirements.txt
export OPENAI_API_KEY=your_key_here  # or add to .env file
```

First run downloads models (~500MB sentence-transformers, ~1.6GB for NLI model). NLTK tokenizers are auto-downloaded on first use.

## Common Commands

```bash
# Web interface
python -m app.main --web

# Analyze a single review (LLM method by default)
python -m app.main --review "The acting was great but the plot was weak."

# Use local NLI method
python -m app.main --review "..." --method "Zero-shot NLI (local)"

# Custom aspects
python -m app.main --review "..." --aspects acting plot soundtrack

# Test with dataset
python -m app.main --dataset-kaggle --test 5
python -m app.main --dataset path/to/IMDB_Dataset.csv --test 5

# Run gold dataset inference (saves to predictions.csv)
python inference/run_inference_on_gold.py

# Evaluate predictions (F1 per aspect)
python evaluation/final_sentiment_analysis.py
```

## Architecture

### Analysis Pipeline

`app/sentiment_analyzer.py` is the core engine. The `analyze()` function is the main entry point — it accepts a review string, list of aspects, and method name, returning a pandas DataFrame.

**NLI method flow:**
1. `preprocessing.py`: clean text → tokenize into sentences
2. `sentiment_analyzer.py`: embed sentences + aspects using `all-MiniLM-L6-v2`
3. Find top-3 sentences most similar to each aspect (cosine similarity)
4. Run NLI on the aspect-focused sentence subset → positive/negative/not_mentioned

**LLM method flow:**
1. Send full review + aspects in a structured prompt to GPT-4o-mini
2. Parse JSON response (handles markdown code fence wrapping)
3. Return sentiment per aspect

### Configuration (`app/config.py`)

All model names, thresholds, and default aspects live here:
- `DEFAULT_ASPECTS`: the 6 aspects used when none specified
- `DEFAULT_NLI_THRESHOLD = 0.55` and `DEFAULT_ZSC_THRESHOLD = 0.6`
- Models: `SENTENCE_TRANSFORMER_MODEL`, `ZERO_SHOT_MODEL`, `OPENAI_MODEL`

### Model Loading

Models are lazily loaded as module-level globals in `sentiment_analyzer.py`. First call loads and caches; subsequent calls reuse the cached instance.

### Evaluation Workflow

1. `inference/run_inference_on_gold.py` reads `data/gold_dataset_aspect_level - gold_dataset_aspect_level.csv`, runs both methods per review, writes `predictions.csv` (checkpoints every 10 reviews)
2. `evaluation/final_sentiment_analysis.py` reads `predictions.csv` and prints macro F1 per aspect

### Entry Point

`app/main.py` handles both CLI (argparse) and Gradio web UI. Always run as `python -m app.main` from project root — direct `python app/main.py` breaks package-relative imports.

## Notes

- `database.py` is incomplete — `save_review()` references a `reviews` table that is never created in `init_database()`
- The README lists 7 default aspects (acting, plot, pacing, soundtrack, directing, cinematography, cast), but `config.py` defines 6 different ones (`acting_performances`, `story_plot`, `pacing`, `visuals`, `directing`, `writing`) — config.py is authoritative
- IMDB scraping via `app/imdb_scraper.py` / `app/run_scrapy.py` outputs to `app/movie_details.json` (gitignored)
