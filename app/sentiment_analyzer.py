"""
Core sentiment analysis functions using LLM and Zero-shot NLI methods.
"""
import asyncio
import re
import json
import pandas as pd
import torch
from sentence_transformers import SentenceTransformer, util
from transformers import pipeline
from openai import OpenAI, AsyncOpenAI

from .config import (
    DEFAULT_ASPECTS,
    DEFAULT_NLI_THRESHOLD,
    DEFAULT_ZSC_THRESHOLD,
    SENTENCE_TRANSFORMER_MODEL,
    ZERO_SHOT_MODEL,
    OPENAI_MODEL,
    OPENAI_MAX_TOKENS,
    get_openai_api_key
)
from .preprocessing import clean_text, get_sentences

# Initialize models (lazy loading)
_sentence_model = None
_zsc_pipeline = None
_openai_client = None
_async_openai_client = None


def _get_sentence_model():
    """Lazy load sentence transformer model."""
    global _sentence_model
    if _sentence_model is None:
        _sentence_model = SentenceTransformer(SENTENCE_TRANSFORMER_MODEL)
    return _sentence_model


def _get_zsc_pipeline():
    """Lazy load zero-shot classification pipeline."""
    global _zsc_pipeline
    if _zsc_pipeline is None:
        _zsc_pipeline = pipeline(
            "zero-shot-classification",
            model=ZERO_SHOT_MODEL,
            device=-1  # Use CPU
        )
    return _zsc_pipeline


def _get_openai_client():
    """Lazy load OpenAI client."""
    global _openai_client
    if _openai_client is None:
        api_key = get_openai_api_key()
        _openai_client = OpenAI(api_key=api_key)
    return _openai_client


def embed_sentences(sentences: list, aspects: list):
    """
    Embed sentences and aspects into vectors.
    
    Args:
        sentences: List of sentences
        aspects: List of aspect names
        
    Returns:
        Tuple of (sentence embeddings, aspect embeddings)
    """
    model = _get_sentence_model()
    sent_emb = model.encode(sentences, convert_to_tensor=True)
    asp_emb = model.encode(aspects, convert_to_tensor=True)
    return sent_emb, asp_emb


def top_k_sentences_per_aspect(sentences: list, sent_emb, aspects: list, asp_emb, k: int = 3):
    """
    Return top k most related sentences to each aspect.
    
    Args:
        sentences: List of sentences
        sent_emb: Sentence embeddings tensor
        aspects: List of aspect names
        asp_emb: Aspect embeddings tensor
        k: Number of top sentences to return per aspect
        
    Returns:
        Dictionary mapping aspect names to lists of top sentences
    """
    # Ensure k doesn't exceed the number of sentences
    num_sentences = len(sentences)
    k = min(k, num_sentences)
    if k <= 0:
        return {aspect: [] for aspect in aspects}
    
    top_sents = {}
    for i, aspect in enumerate(aspects):
        sims = util.cos_sim(asp_emb[i], sent_emb)[0]
        topk_idx = torch.topk(sims, k).indices
        top_sents[aspect] = [sentences[j] for j in topk_idx]
    return top_sents


def concat_asp_sentences(top3: dict) -> dict:
    """
    Concatenate sentences for each aspect.
    
    Args:
        top3: Dictionary mapping aspects to lists of sentences
        
    Returns:
        Dictionary mapping aspects to concatenated text
    """
    concatenated = {}
    for aspect, sents in top3.items():
        concatenated[aspect] = " ".join(sents)
    return concatenated


def nli_aspect_sentiment(review: str, aspects: list = None, threshold: float = None):
    """
    Analyze aspect-based sentiment using Zero-shot NLI (local model).
    
    Args:
        review: Review text to analyze
        aspects: List of aspects to analyze (defaults to DEFAULT_ASPECTS)
        threshold: Confidence threshold (defaults to DEFAULT_NLI_THRESHOLD)
        
    Returns:
        List of dictionaries with aspect, sentiment, and confidence
    """
    if aspects is None:
        aspects = DEFAULT_ASPECTS
    if threshold is None:
        threshold = DEFAULT_NLI_THRESHOLD
        
    sentiments = ["positive", "negative", "not_mentioned"]
    rows = []
    
    # Initialize cleaned before try block to ensure it's always defined
    cleaned = review
    
    try:
        # Clean and split
        cleaned = clean_text(review)
        sentences = get_sentences(cleaned)

        # Process short reviews all together
        if len(sentences) <= 3:
            aspect_snippets = {a: cleaned for a in aspects}
        else:
            # Embed and find top k sentences
            sent_emb, asp_emb = embed_sentences(sentences, aspects)
            top3 = top_k_sentences_per_aspect(sentences, sent_emb, aspects, asp_emb, k=3)
            aspect_snippets = concat_asp_sentences(top3)

    except Exception as e:
        print(f"Preprocessing failed: {e}. Falling back to full review.")
        # Use cleaned (which defaults to review if clean_text failed)
        aspect_snippets = {a: cleaned for a in aspects}

    zsc = _get_zsc_pipeline()
    
    for a in aspects:
        try:
            focused_text = aspect_snippets.get(a, review)

            res = zsc(
                focused_text,
                candidate_labels=sentiments,
                hypothesis_template=f"The sentiment towards {a} is {{}}."
            )

            label, score = res["labels"][0], float(res["scores"][0])

            if score < threshold:
                label = "not_mentioned"
            rows.append({"aspect": a, "sentiment": label, "confidence": round(score, 3)})
        except Exception as e:
            print(f"Error processing aspect '{a}': {e}")
            rows.append({"aspect": a, "sentiment": "error", "confidence": 0.0})
    
    return rows


def llm_aspect_sentiment(review: str, aspects: list = None, max_tokens: int = None, domain: str = "product"):
    """
    Analyze aspect-based sentiment using OpenAI LLM.

    Args:
        review: Review text to analyze
        aspects: List of aspects to analyze (defaults to DEFAULT_ASPECTS)
        max_tokens: Maximum tokens for response (defaults to OPENAI_MAX_TOKENS)
        domain: The domain/type of review (e.g. "movie", "restaurant", "software")

    Returns:
        List of dictionaries with aspect and sentiment
    """
    if aspects is None:
        aspects = DEFAULT_ASPECTS
    if max_tokens is None:
        max_tokens = OPENAI_MAX_TOKENS

    client = _get_openai_client()

    prompt = f"""
You are analyzing a {domain} review for aspect-based sentiment.
Aspects: {", ".join(aspects)}.
For each aspect, return one of: "positive","negative","not_mentioned".
- "positive": the review expresses a favorable opinion about this aspect
- "negative": the review expresses an unfavorable opinion about this aspect
- "not_mentioned": the review does not discuss this aspect at all
Return STRICT JSON ONLY as an array of objects:
[{{"aspect":"acting","sentiment":"positive"}}, ...]
Review:
{review}
""".strip()

    resp = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
        max_tokens=max_tokens,
    )

    txt = resp.choices[0].message.content.strip()

    # Try direct JSON parse first
    try:
        return json.loads(txt)
    except json.JSONDecodeError:
        # If the model accidentally wrapped in ```json fences, strip them & keep just the array
        try:
            txt_clean = re.sub(r"^```json\s*|\s*```$", "", txt, flags=re.I).strip()
            start, end = txt_clean.find("["), txt_clean.rfind("]")
            if start != -1 and end != -1:
                txt_clean = txt_clean[start: end + 1]
            return json.loads(txt_clean)
        except (json.JSONDecodeError, ValueError) as e:
            # If all parsing attempts fail, raise a more informative error
            raise ValueError(
                f"Failed to parse OpenAI response as JSON. Response was: {txt[:200]}..."
            ) from e


def _get_async_openai_client():
    """Lazy load async OpenAI client."""
    global _async_openai_client
    if _async_openai_client is None:
        api_key = get_openai_api_key()
        _async_openai_client = AsyncOpenAI(api_key=api_key)
    return _async_openai_client


async def async_llm_aspect_sentiment(
    review: str,
    aspects: list = None,
    max_tokens: int = None,
    domain: str = "product",
) -> list[dict]:
    """
    Async version of llm_aspect_sentiment using AsyncOpenAI.
    """
    if aspects is None:
        aspects = DEFAULT_ASPECTS
    if max_tokens is None:
        max_tokens = OPENAI_MAX_TOKENS

    client = _get_async_openai_client()

    prompt = f"""
You are analyzing a {domain} review for aspect-based sentiment.
Aspects: {", ".join(aspects)}.
For each aspect, return one of: "positive","negative","not_mentioned".
- "positive": the review expresses a favorable opinion about this aspect
- "negative": the review expresses an unfavorable opinion about this aspect
- "not_mentioned": the review does not discuss this aspect at all
Return STRICT JSON ONLY as an array of objects:
[{{"aspect":"acting","sentiment":"positive"}}, ...]
Review:
{review}
""".strip()

    resp = await client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
        max_tokens=max_tokens,
    )

    txt = resp.choices[0].message.content.strip()

    try:
        return json.loads(txt)
    except json.JSONDecodeError:
        try:
            txt_clean = re.sub(r"^```json\s*|\s*```$", "", txt, flags=re.I).strip()
            start, end = txt_clean.find("["), txt_clean.rfind("]")
            if start != -1 and end != -1:
                txt_clean = txt_clean[start: end + 1]
            return json.loads(txt_clean)
        except (json.JSONDecodeError, ValueError) as e:
            raise ValueError(
                f"Failed to parse OpenAI response as JSON. Response was: {txt[:200]}..."
            ) from e


async def async_analyze_batch(
    reviews: list[str],
    aspects: list[str] = None,
    domain: str = "movie",
    max_concurrency: int = 10,
    on_progress: callable = None,
) -> list[list[dict]]:
    """
    Analyze a batch of reviews concurrently using the async OpenAI client.

    Args:
        reviews: List of review texts
        aspects: Aspects to analyze
        domain: Domain label
        max_concurrency: Max concurrent API calls
        on_progress: Optional callback(completed, total) called after each review

    Returns:
        List of result lists, one per review
    """
    if not aspects:
        aspects = DEFAULT_ASPECTS

    semaphore = asyncio.Semaphore(max_concurrency)
    results = [None] * len(reviews)
    completed = 0

    async def _analyze_one(idx: int, review: str):
        nonlocal completed
        async with semaphore:
            try:
                result = await async_llm_aspect_sentiment(
                    review, aspects, domain=domain
                )
            except Exception as e:
                # On failure, return not_mentioned for all aspects
                result = [
                    {"aspect": a, "sentiment": "not_mentioned"} for a in aspects
                ]
            results[idx] = result
            completed += 1
            if on_progress:
                on_progress(completed, len(reviews))

    await asyncio.gather(
        *[_analyze_one(i, r) for i, r in enumerate(reviews)]
    )
    return results


def analyze(review: str, aspects: list = None, method: str = "LLM (OpenAI)", domain: str = "product"):
    """
    Analyze review sentiment for given aspects using specified method.

    Args:
        review: Review text to analyze
        aspects: List of aspects to analyze (defaults to DEFAULT_ASPECTS)
        method: Analysis method - "LLM (OpenAI)" or "Zero-shot NLI (local)"
        domain: The domain/type of review (e.g. "movie", "restaurant", "software")

    Returns:
        pandas DataFrame with aspect and sentiment columns
    """
    try:
        if not review:
            return pd.DataFrame([{"aspect": "", "sentiment": "(no review)"}])

        if not aspects:
            aspects = DEFAULT_ASPECTS

        if method == "LLM (OpenAI)":
            data = llm_aspect_sentiment(review, aspects, domain=domain)
        else:  # Zero-shot NLI
            data = nli_aspect_sentiment(review, aspects)

        rows = [
            {
                "aspect": d.get("aspect", ""),
                "sentiment": d.get("sentiment", ""),
            }
            for d in data
        ]
        return pd.DataFrame(rows)

    except Exception as e:
        # Show error context directly in output
        return pd.DataFrame(
            [{"aspect": "(error)", "sentiment": f"{type(e).__name__}: {e}"}]
        )

