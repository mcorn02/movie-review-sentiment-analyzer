"""
Main entry point for the product_reviewer application.
"""
import argparse
import os
import sys
import pandas as pd

try:
    import kagglehub
except ImportError:
    kagglehub = None

from .config import DEFAULT_ASPECTS
from .sentiment_analyzer import analyze
from .report_generator import generate_report, format_report_markdown


def load_dataset_kaggle(dataset_name: str = "lakshmi25npathi/imdb-dataset-of-50k-movie-reviews"):
    """
    Load dataset from Kaggle using kagglehub.

    Args:
        dataset_name: Kaggle dataset identifier

    Returns:
        pandas DataFrame or None if download fails
    """
    if kagglehub is None:
        print("Warning: kagglehub not installed. Install with: pip install kagglehub")
        return None

    try:
        print(f"Downloading dataset from Kaggle: {dataset_name}")
        path = kagglehub.dataset_download(dataset_name)
        print(f"Dataset downloaded to: {path}")

        # Find CSV file in downloaded directory
        csv_file = None
        for root, dirs, files in os.walk(path):
            for file in files:
                if file.endswith('.csv') and 'IMDB' in file:
                    csv_file = os.path.join(root, file)
                    break
            if csv_file:
                break

        if csv_file:
            print(f"Loading CSV file: {csv_file}")
            df = pd.read_csv(csv_file, encoding='latin-1')
            return df
        else:
            print("Warning: Could not find IMDB Dataset.csv in downloaded files")
            return None
    except Exception as e:
        print(f"Error downloading from Kaggle: {e}")
        return None


def load_dataset_manual(file_path: str):
    """
    Load dataset from a local file path.

    Args:
        file_path: Path to CSV file

    Returns:
        pandas DataFrame or None if loading fails
    """
    try:
        if not os.path.exists(file_path):
            print(f"Error: File not found: {file_path}")
            return None
        print(f"Loading dataset from: {file_path}")
        df = pd.read_csv(file_path, encoding='latin-1')
        return df
    except Exception as e:
        print(f"Error loading dataset: {e}")
        return None


def analyze_review_cli(review: str, aspects: list, method: str):
    """
    Analyze a single review via CLI.

    Args:
        review: Review text
        aspects: List of aspects to analyze
        method: Analysis method
    """
    print(f"\nAnalyzing review using {method}...")
    print(f"Aspects: {', '.join(aspects)}")
    print(f"\nReview:\n{review}\n")
    print("-" * 80)

    df = analyze(review, aspects, method)
    print("\nResults:")
    print(df.to_string(index=False))
    print()


def main():
    """Main function to run the product reviewer application."""
    parser = argparse.ArgumentParser(
        description="Aspect-based sentiment analysis for movie reviews"
    )
    parser.add_argument(
        "--web",
        action="store_true",
        help="Launch FastAPI web server"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port for the web server (default: 8000)"
    )
    parser.add_argument(
        "--review",
        type=str,
        help="Review text to analyze (for CLI mode)"
    )
    parser.add_argument(
        "--file",
        type=str,
        help="Path to file containing review text"
    )
    parser.add_argument(
        "--dataset",
        type=str,
        help="Path to IMDB dataset CSV file (for testing)"
    )
    parser.add_argument(
        "--dataset-kaggle",
        action="store_true",
        help="Download dataset from Kaggle (requires kagglehub)"
    )
    parser.add_argument(
        "--aspects",
        nargs="+",
        default=DEFAULT_ASPECTS,
        help=f"Aspects to analyze (default: {DEFAULT_ASPECTS})"
    )
    parser.add_argument(
        "--method",
        choices=["LLM (OpenAI)", "Zero-shot NLI (local)"],
        default="LLM (OpenAI)",
        help="Analysis method to use"
    )
    parser.add_argument(
        "--test",
        type=int,
        metavar="N",
        help="Test with first N reviews from dataset"
    )

    args = parser.parse_args()

    # Launch web server (FastAPI)
    if args.web:
        import uvicorn
        print(f"Starting FastAPI server on http://localhost:{args.port}")
        print("API docs available at /docs")
        uvicorn.run("api.main:app", host="0.0.0.0", port=args.port, reload=True)
        return

    # CLI mode
    review_text = None

    # Get review from various sources
    if args.review:
        review_text = args.review
    elif args.file:
        try:
            with open(args.file, 'r', encoding='utf-8') as f:
                review_text = f.read()
        except Exception as e:
            print(f"Error reading file: {e}")
            sys.exit(1)
    elif args.dataset or args.dataset_kaggle or args.test:
        # Load dataset for testing
        df = None
        if args.dataset:
            df = load_dataset_manual(args.dataset)
        elif args.dataset_kaggle:
            df = load_dataset_kaggle()

        if df is None and args.test:
            print("Error: Could not load dataset. Use --dataset or --dataset-kaggle")
            sys.exit(1)

        if args.test:
            if df is None:
                print("Error: Dataset required for --test. Use --dataset or --dataset-kaggle")
                sys.exit(1)
            num_reviews = args.test
            test_reviews = df['review'].head(num_reviews).tolist()
            print(f"\nTesting with {num_reviews} reviews from dataset...\n")
            for i, review in enumerate(test_reviews, 1):
                print(f"\n{'='*80}")
                print(f"Review {i}/{num_reviews}")
                print(f"{'='*80}")
                analyze_review_cli(review, args.aspects, args.method)
            return
        else:
            # If dataset loaded but no test, use first review
            if df is not None:
                review_text = df['review'].iloc[0]
                print("Using first review from dataset (use --test N for multiple reviews)")

    # Analyze single review
    if review_text:
        analyze_review_cli(review_text, args.aspects, args.method)
    else:
        # No input provided, show help
        parser.print_help()
        print("\nExamples:")
        print("  # Launch web server:")
        print("  python -m app.main --web")
        print("\n  # Analyze a review:")
        print("  python -m app.main --review 'This movie was great!'")
        print("\n  # Test with dataset:")
        print("  python -m app.main --dataset-kaggle --test 5")


if __name__ == "__main__":
    main()
