"""
Text preprocessing functions for sentiment analysis.
"""
import re
import nltk
from nltk.tokenize import sent_tokenize

# Download NLTK data if not already present
try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    nltk.download('punkt', quiet=True)

try:
    nltk.data.find('tokenizers/punkt_tab')
except LookupError:
    nltk.download('punkt_tab', quiet=True)


def clean_text(review: str) -> str:
    """
    Clean text by removing HTML line breaks and normalizing spacing.
    
    Args:
        review: Raw review text
        
    Returns:
        Cleaned review text
    """
    # Remove HTML line breaks
    cleaned = re.sub(r"<br\s*/?>", " ", review)  # handles <br>, <br/>, <br />, etc.

    # Add a space after punctuation if not followed by space, digit, or end of string
    cleaned = re.sub(r'([.!?])(?=[A-Za-z])', r'\1 ', cleaned)

    # Collapse multiple spaces into one
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    return cleaned


def get_sentences(text: str) -> list:
    """
    Split text into sentences using NLTK tokenizer.
    
    Args:
        text: Input text
        
    Returns:
        List of sentences
    """
    return sent_tokenize(text)

