# Product Reviewer - Aspect-Based Sentiment Analysis

A Python application for performing aspect-based sentiment analysis on movie reviews using two methods:
- **LLM (OpenAI)**: Uses GPT-4o-mini for sentiment classification
- **Zero-shot NLI (local)**: Uses Facebook BART-large-MNLI model running locally

## Features

- Analyze sentiment for multiple aspects (acting, plot, pacing, soundtrack, direction, cinematography, cast)
- Two analysis methods: OpenAI LLM or local zero-shot NLI
- Web interface via Gradio
- Command-line interface for batch processing
- Support for Kaggle dataset download or local CSV files

## Installation

1. Create a virtual environment (recommended):
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set up your OpenAI API key (required for LLM method):

   **Option 1: Environment variable (recommended)**
   ```bash
   export OPENAI_API_KEY=your_api_key_here
   ```

   **Option 2: .env file**
   Create a `.env` file in the project root:
   ```
   OPENAI_API_KEY=your_api_key_here
   ```

   Get your API key from: https://platform.openai.com/api-keys

## Usage

### Web Interface

Launch the Gradio web interface:
```bash
python main.py --web
```

This will start a local web server where you can:
- Paste movie reviews
- Select aspects to analyze
- Choose between LLM or NLI methods
- View results in a table

### Command-Line Interface

**Analyze a single review:**
```bash
python main.py --review "This movie had great acting but a weak plot."
```

**Analyze from a file:**
```bash
python main.py --file review.txt
```

**Test with dataset:**
```bash
# Download from Kaggle and test with 5 reviews
python main.py --dataset-kaggle --test 5

# Use local dataset file
python main.py --dataset path/to/IMDB_Dataset.csv --test 5
```

**Custom aspects:**
```bash
python main.py --review "..." --aspects acting plot soundtrack
```

**Choose method:**
```bash
python main.py --review "..." --method "Zero-shot NLI (local)"
```

### Command-Line Options

- `--web`: Launch Gradio web interface
- `--review TEXT`: Review text to analyze
- `--file PATH`: Path to file containing review text
- `--dataset PATH`: Path to IMDB dataset CSV file
- `--dataset-kaggle`: Download dataset from Kaggle (requires kagglehub)
- `--aspects ASPECT1 ASPECT2 ...`: Custom aspects to analyze
- `--method METHOD`: Analysis method ("LLM (OpenAI)" or "Zero-shot NLI (local)")
- `--test N`: Test with first N reviews from dataset

## Project Structure

```
product_reviewer/
├── __init__.py
├── main.py              # Entry point with CLI and Gradio interface
├── config.py            # Configuration and API key management
├── preprocessing.py     # Text cleaning and sentence tokenization
├── sentiment_analyzer.py # Core sentiment analysis functions
├── requirements.txt     # Python dependencies
└── README.md           # This file
```

## Methods Comparison

### LLM (OpenAI)
- **Pros**: High accuracy, understands context well, fast API calls
- **Cons**: Requires API key, costs money per request, requires internet
- **Best for**: Production use, high accuracy requirements

### Zero-shot NLI (local)
- **Pros**: Free, works offline, no API limits, privacy-preserving
- **Cons**: Slower (runs locally), requires more memory, slightly lower accuracy
- **Best for**: Development, privacy-sensitive applications, offline use

## Dataset

The application supports the IMDB Dataset of 50K Movie Reviews from Kaggle:
- Dataset: `lakshmi25npathi/imdb-dataset-of-50k-movie-reviews`
- Automatic download via `kagglehub` (requires Kaggle credentials)
- Manual CSV file path also supported

## Default Aspects

The application analyzes these aspects by default:
- acting
- plot
- pacing
- soundtrack
- direction
- cinematography
- cast

You can specify custom aspects using the `--aspects` flag or in the web interface.

## Troubleshooting

**OpenAI API key not found:**
- Ensure `OPENAI_API_KEY` is set as environment variable or in `.env` file
- Check that `.env` file is in the project root directory

**NLTK data missing:**
- The application will automatically download required NLTK data on first run
- If download fails, manually run: `python -c "import nltk; nltk.download('punkt'); nltk.download('punkt_tab')"`

**Model download issues:**
- First run will download models (~500MB for sentence-transformers, ~1.6GB for BART)
- Ensure sufficient disk space and internet connection
- Models are cached for subsequent runs

**Kaggle dataset download:**
- Requires `kagglehub` package (included in requirements.txt)
- May require Kaggle API credentials (see kagglehub documentation)
- Fallback to manual dataset path if download fails

## License

Add your license information here.
