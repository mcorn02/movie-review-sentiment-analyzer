"""
Configuration management and API key loading.
"""
import os
from dotenv import load_dotenv

# Load environment variables from .env file if it exists
load_dotenv()

# Default aspects for sentiment analysis
DEFAULT_ASPECTS = [
    "acting_performances",
    "story_plot",
    "pacing",
    "visuals",
    "direction",
    "writing"
]

# Default thresholds
DEFAULT_NLI_THRESHOLD = 0.55
DEFAULT_ZSC_THRESHOLD = 0.6

# Model configuration
SENTENCE_TRANSFORMER_MODEL = "all-MiniLM-L6-v2"
ZERO_SHOT_MODEL = "typeform/distilbert-base-uncased-mnli"
OPENAI_MODEL = "gpt-4o-mini"
OPENAI_MAX_TOKENS = 180


def get_openai_api_key():
    """
    Get OpenAI API key from environment variable or .env file.
    
    Returns:
        str: OpenAI API key
        
    Raises:
        ValueError: If API key is not found
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError(
            "OpenAI API key not found. Please set OPENAI_API_KEY environment variable "
            "or add it to a .env file in the project root."
        )
    return api_key

