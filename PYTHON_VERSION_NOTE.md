# Python Version Compatibility Note

## Important: PyTorch and Python 3.13

**Current Status**: PyTorch does not yet have official builds for Python 3.13.

The following packages require PyTorch and cannot be installed on Python 3.13:
- `torch` (PyTorch)
- `transformers` (depends on torch)
- `sentence-transformers` (depends on torch)

## Solutions

### Option 1: Use Python 3.12 or 3.11 (Recommended)

Create a new virtual environment with Python 3.12 or 3.11:

```bash
# If you have Python 3.12 installed:
python3.12 -m venv venv

# Or Python 3.11:
python3.11 -m venv venv

# Then activate and install:
source venv/bin/activate
pip install -r requirements.txt
```

### Option 2: Wait for PyTorch Python 3.13 Support

PyTorch support for Python 3.13 is expected in a future release. Check the [PyTorch website](https://pytorch.org/) for updates.

### Option 3: Use LLM Method Only (Partial Functionality)

If you only need the OpenAI LLM method (not the local NLI method), you can use the application without PyTorch:

```bash
# Already installed packages work fine:
# - pandas
# - nltk  
# - openai
# - gradio
# - kagglehub
# - python-dotenv

# The LLM method will work, but Zero-shot NLI (local) will not.
```

## Current Installation Status

The following packages have been successfully installed:
- ✅ pandas
- ✅ nltk
- ✅ openai
- ✅ gradio
- ✅ kagglehub
- ✅ python-dotenv

The following packages are pending PyTorch support:
- ❌ torch (requires Python 3.12 or earlier)
- ❌ transformers (requires torch)
- ❌ sentence-transformers (requires torch)

