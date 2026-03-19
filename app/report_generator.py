"""
RAG-based report generation over a corpus of reviews.

Builds an embedding index of all review sentences, retrieves the most relevant
snippets per aspect, and uses an LLM to produce a grounded narrative report.
"""
import asyncio
import numpy as np
import pandas as pd
from sentence_transformers import util

from .config import DEFAULT_ASPECTS, OPENAI_MODEL, OPENAI_MAX_TOKENS, get_openai_api_key
from .preprocessing import clean_text, get_sentences
from .sentiment_analyzer import (
    _get_sentence_model,
    _get_openai_client,
    _get_async_openai_client,
    analyze,
    async_analyze_batch,
)


def build_corpus(reviews: list[str]) -> dict:
    """
    Sentence-tokenize and embed every review into a searchable corpus.

    Returns:
        dict with keys:
        - sentences: list[str]
        - review_indices: list[int]  (which review each sentence came from)
        - embeddings: np.ndarray of shape (n_sentences, dim)
    """
    model = _get_sentence_model()
    all_sentences = []
    review_indices = []

    for idx, review in enumerate(reviews):
        cleaned = clean_text(review)
        sents = get_sentences(cleaned)
        all_sentences.extend(sents)
        review_indices.extend([idx] * len(sents))

    embeddings = model.encode(all_sentences, convert_to_numpy=True)

    return {
        "sentences": all_sentences,
        "review_indices": review_indices,
        "embeddings": embeddings,
    }


def retrieve_for_aspect(aspect: str, corpus: dict, k: int = 10) -> list[dict]:
    """
    Retrieve the top-k most relevant sentences for an aspect.

    Returns list of dicts: [{sentence, review_idx, score}, ...]
    """
    model = _get_sentence_model()
    asp_emb = model.encode([aspect], convert_to_numpy=True)
    scores = util.cos_sim(asp_emb, corpus["embeddings"])[0].numpy()

    k = min(k, len(scores))
    top_indices = np.argsort(scores)[::-1][:k]

    results = []
    for i in top_indices:
        results.append({
            "sentence": corpus["sentences"][i],
            "review_idx": corpus["review_indices"][i],
            "score": float(scores[i]),
        })
    return results


def _compute_distribution(aspect_results: list[dict]) -> dict:
    """Count sentiment distribution for a single aspect across all reviews."""
    counts = {"positive": 0, "negative": 0, "not_mentioned": 0}
    for r in aspect_results:
        sentiment = r.get("sentiment", "not_mentioned")
        if sentiment in counts:
            counts[sentiment] += 1
        else:
            counts["not_mentioned"] += 1
    total = sum(counts.values()) or 1
    return {k: {"count": v, "pct": round(v / total * 100, 1)} for k, v in counts.items()}


def generate_aspect_section(
    aspect: str,
    retrieved: list[dict],
    distribution: dict,
) -> str:
    """
    Use the LLM to write a narrative section for one aspect, grounded in
    retrieved review quotes.
    """
    client = _get_openai_client()

    pos_pct = distribution["positive"]["pct"]
    neg_pct = distribution["negative"]["pct"]
    nm_pct = distribution["not_mentioned"]["pct"]

    quotes_block = "\n".join(
        f'- (review #{r["review_idx"] + 1}, relevance {r["score"]:.2f}) "{r["sentence"]}"'
        for r in retrieved
    )

    prompt = f"""You are writing a section of a review analysis report about the aspect "{aspect}".

Sentiment distribution across all reviews:
  Positive: {pos_pct}%  |  Negative: {neg_pct}%  |  Not mentioned: {nm_pct}%

Below are the most relevant sentences from the review corpus for this aspect.
Use them as evidence — quote directly when helpful.

{quotes_block}

Write a concise 2-4 sentence summary of what reviewers praised and criticized
about "{aspect}". Reference specific quotes. Do not invent details beyond the
provided quotes. Start directly with the findings — no preamble."""

    resp = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        max_tokens=OPENAI_MAX_TOKENS,
    )
    return resp.choices[0].message.content.strip()


def generate_report(
    reviews: list[str],
    aspects: list[str] | None = None,
    method: str = "LLM (OpenAI)",
) -> dict:
    """
    End-to-end report generation over a corpus of reviews.

    Returns:
        dict with keys:
        - n_reviews: int
        - aspects: list of aspect report dicts, each containing:
            - name, distribution, narrative, top_quotes
        - overall_summary: str
    """
    if not aspects:
        aspects = DEFAULT_ASPECTS

    # Step 1: Run sentiment analysis on every review
    all_results = []  # list of list-of-dicts, one per review
    for review in reviews:
        df = analyze(review, aspects, method)
        all_results.append(df.to_dict("records"))

    # Step 2: Build RAG corpus
    corpus = build_corpus(reviews)

    # Step 3: Per-aspect retrieval + narrative
    aspect_reports = []
    for aspect in aspects:
        # Gather sentiment labels for this aspect across reviews
        aspect_sentiments = []
        for review_results in all_results:
            for r in review_results:
                if r["aspect"] == aspect:
                    aspect_sentiments.append(r)

        distribution = _compute_distribution(aspect_sentiments)
        retrieved = retrieve_for_aspect(aspect, corpus, k=10)

        narrative = generate_aspect_section(aspect, retrieved, distribution)

        aspect_reports.append({
            "name": aspect,
            "distribution": distribution,
            "narrative": narrative,
            "top_quotes": [
                {"sentence": r["sentence"], "review": r["review_idx"] + 1}
                for r in retrieved[:5]
            ],
        })

    # Step 4: Overall summary
    client = _get_openai_client()
    summary_lines = []
    for ar in aspect_reports:
        d = ar["distribution"]
        summary_lines.append(
            f'- {ar["name"]}: {d["positive"]["pct"]}% positive, '
            f'{d["negative"]["pct"]}% negative, '
            f'{d["not_mentioned"]["pct"]}% not mentioned'
        )
    summary_prompt = f"""You are summarizing a review analysis report across {len(reviews)} reviews.

Aspect-level sentiment breakdown:
{chr(10).join(summary_lines)}

Write a concise 2-3 sentence overall summary highlighting what is working well
and what needs improvement. Be direct and specific."""

    resp = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[{"role": "user", "content": summary_prompt}],
        temperature=0.3,
        max_tokens=200,
    )

    return {
        "n_reviews": len(reviews),
        "aspects": aspect_reports,
        "overall_summary": resp.choices[0].message.content.strip(),
    }


async def async_generate_aspect_section(
    aspect: str,
    retrieved: list[dict],
    distribution: dict,
) -> str:
    """Async version of generate_aspect_section."""
    client = _get_async_openai_client()

    pos_pct = distribution["positive"]["pct"]
    neg_pct = distribution["negative"]["pct"]
    nm_pct = distribution["not_mentioned"]["pct"]

    quotes_block = "\n".join(
        f'- (review #{r["review_idx"] + 1}, relevance {r["score"]:.2f}) "{r["sentence"]}"'
        for r in retrieved
    )

    prompt = f"""You are writing a section of a review analysis report about the aspect "{aspect}".

Sentiment distribution across all reviews:
  Positive: {pos_pct}%  |  Negative: {neg_pct}%  |  Not mentioned: {nm_pct}%

Below are the most relevant sentences from the review corpus for this aspect.
Use them as evidence — quote directly when helpful.

{quotes_block}

Write a concise 2-4 sentence summary of what reviewers praised and criticized
about "{aspect}". Reference specific quotes. Do not invent details beyond the
provided quotes. Start directly with the findings — no preamble."""

    resp = await client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        max_tokens=OPENAI_MAX_TOKENS,
    )
    return resp.choices[0].message.content.strip()


async def async_generate_report(
    reviews: list[str],
    aspects: list[str] | None = None,
    on_stage: callable = None,
) -> dict:
    """
    Async end-to-end report generation with streaming callbacks.

    Args:
        reviews: List of review texts
        aspects: Aspects to analyze (defaults to DEFAULT_ASPECTS)
        on_stage: Optional async callback(stage, data) for progress updates

    Returns:
        dict with n_reviews, aspects (list of aspect reports), overall_summary
    """
    if not aspects:
        aspects = DEFAULT_ASPECTS

    async def _notify(stage, data=None):
        if on_stage:
            await on_stage(stage, data)

    # Step 1: Concurrent sentiment analysis
    await _notify("analyzing", {"progress": 0, "total": len(reviews)})

    def _on_analysis_progress(completed, total):
        # Can't await in a sync callback, so we skip SSE updates here.
        # The caller gets the final result.
        pass

    all_results = await async_analyze_batch(
        reviews, aspects, domain="movie", on_progress=_on_analysis_progress,
    )

    await _notify("analyzing", {"progress": len(reviews), "total": len(reviews)})

    # Step 2: Build RAG corpus (CPU-bound, fast enough sync)
    await _notify("generating", {"message": "Building embedding index..."})
    corpus = build_corpus(reviews)

    # Step 3: Per-aspect retrieval + narrative (concurrent LLM calls)
    await _notify("generating", {"message": "Generating aspect narratives..."})

    aspect_data = []
    for aspect in aspects:
        aspect_sentiments = []
        for review_results in all_results:
            for r in review_results:
                if r["aspect"] == aspect:
                    aspect_sentiments.append(r)
        distribution = _compute_distribution(aspect_sentiments)
        retrieved = retrieve_for_aspect(aspect, corpus, k=10)
        aspect_data.append((aspect, retrieved, distribution))

    # Generate all aspect sections concurrently
    narratives = await asyncio.gather(
        *[
            async_generate_aspect_section(aspect, retrieved, distribution)
            for aspect, retrieved, distribution in aspect_data
        ]
    )

    aspect_reports = []
    for i, (aspect, retrieved, distribution) in enumerate(aspect_data):
        report_entry = {
            "name": aspect,
            "distribution": distribution,
            "narrative": narratives[i],
            "top_quotes": [
                {"sentence": r["sentence"], "review": r["review_idx"] + 1}
                for r in retrieved[:5]
            ],
        }
        aspect_reports.append(report_entry)
        await _notify("aspect_complete", report_entry)

    # Step 4: Overall summary
    await _notify("generating", {"message": "Writing overall summary..."})
    client = _get_async_openai_client()

    summary_lines = []
    for ar in aspect_reports:
        d = ar["distribution"]
        summary_lines.append(
            f'- {ar["name"]}: {d["positive"]["pct"]}% positive, '
            f'{d["negative"]["pct"]}% negative, '
            f'{d["not_mentioned"]["pct"]}% not mentioned'
        )

    summary_prompt = f"""You are summarizing a review analysis report across {len(reviews)} reviews.

Aspect-level sentiment breakdown:
{chr(10).join(summary_lines)}

Write a concise 2-3 sentence overall summary highlighting what is working well
and what needs improvement. Be direct and specific."""

    resp = await client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[{"role": "user", "content": summary_prompt}],
        temperature=0.3,
        max_tokens=200,
    )

    return {
        "n_reviews": len(reviews),
        "aspects": aspect_reports,
        "overall_summary": resp.choices[0].message.content.strip(),
    }


def format_report_markdown(report: dict) -> str:
    """Convert a report dict into a readable Markdown string."""
    lines = []
    lines.append(f"# Review Analysis Report ({report['n_reviews']} reviews)\n")
    lines.append(f"## Overall Summary\n\n{report['overall_summary']}\n")

    for ar in report["aspects"]:
        d = ar["distribution"]
        lines.append(f"## {ar['name']}\n")
        lines.append(
            f"**Sentiment distribution:** "
            f"{d['positive']['pct']}% positive · "
            f"{d['negative']['pct']}% negative · "
            f"{d['not_mentioned']['pct']}% not mentioned\n"
        )
        lines.append(f"{ar['narrative']}\n")
        lines.append("**Top quotes:**\n")
        for q in ar["top_quotes"]:
            lines.append(f'- _(review #{q["review"]})_ "{q["sentence"]}"')
        lines.append("")

    return "\n".join(lines)
