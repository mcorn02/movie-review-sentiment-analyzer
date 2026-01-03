"""
Main entry point for the product_reviewer application.
"""
import argparse
import os
import sys
import pandas as pd

try:
    import gradio as gr
except ImportError:
    gr = None

try:
    import kagglehub
except ImportError:
    kagglehub = None

from .config import DEFAULT_ASPECTS
from .sentiment_analyzer import analyze


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


def create_gradio_interface():
    """Create and return Gradio interface."""
    if gr is None:
        raise ImportError(
            "Gradio is not installed. Install it with: pip install gradio"
        )
    with gr.Blocks(title="Aspect Sentiment: LLM vs NLI") as demo:
        gr.Markdown("## Aspect-Based Sentiment — Compare Methods")

        review_in = gr.Textbox(
            label="Review",
            lines=8,
            placeholder="Paste a movie review…"
        )
        aspects_in = gr.CheckboxGroup(
            choices=DEFAULT_ASPECTS,
            value=DEFAULT_ASPECTS,
            label="Aspects"
        )
        method_in = gr.Radio(
            choices=["LLM (OpenAI)", "Zero-shot NLI (local)"],
            value="LLM (OpenAI)",
            label="Method"
        )

        run_btn = gr.Button("Analyze", variant="primary")
        out_df = gr.Dataframe(
            headers=["aspect", "sentiment"],
            label="Results",
            interactive=False
        )

        run_btn.click(fn=analyze, inputs=[review_in, aspects_in, method_in], outputs=out_df)
    
    return demo


def main():
    """Main function to run the product reviewer application."""
    parser = argparse.ArgumentParser(
        description="Aspect-based sentiment analysis for movie reviews"
    )
    parser.add_argument(
        "--web",
        action="store_true",
        help="Launch Gradio web interface"
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

    # Launch web interface
    if args.web:
        if gr is None:
            print("Error: Gradio is not installed. Install it with: pip install gradio")
            sys.exit(1)
        print("Launching Gradio web interface...")
        demo = create_gradio_interface()
        demo.launch(share=False)
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
        print("  # Launch web interface:")
        print("  python main.py --web")
        print("\n  # Analyze a review:")
        print("  python main.py --review 'This movie was great!'")
        print("\n  # Test with dataset:")
        print("  python main.py --dataset-kaggle --test 5")


if __name__ == "__main__":
    main()
