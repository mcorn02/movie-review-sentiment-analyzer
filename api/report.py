"""
Report aggregation: aspect breakdowns, pain points, and LLM theme summary.
"""
from __future__ import annotations
import json
from collections import defaultdict

from openai import OpenAI

from app.config import get_openai_api_key, OPENAI_MODEL


def _get_openai_client() -> OpenAI:
    return OpenAI(api_key=get_openai_api_key())


def build_report(
    predictions: list[dict],
    domain: str,
    aspects: list[str],
    include_llm_summary: bool = True,
) -> dict:
    """
    Aggregate per-review predictions into a business report.

    Args:
        predictions: list of {review_index, review_snippet, results: [{aspect, sentiment}]}
        domain: domain label for LLM context
        aspects: ordered list of aspects
        include_llm_summary: whether to call LLM for a natural-language summary

    Returns:
        dict matching the Report model schema
    """
    total = len(predictions)

    # Collect counts and negative quotes per aspect
    counts: dict[str, dict[str, int]] = {
        a: {"positive": 0, "negative": 0, "not_mentioned": 0} for a in aspects
    }
    negative_snippets: dict[str, list[str]] = defaultdict(list)

    for pred in predictions:
        snippet = pred["review_snippet"]
        for r in pred["results"]:
            asp = r["aspect"]
            sent = r["sentiment"]
            if asp in counts:
                bucket = sent if sent in counts[asp] else "not_mentioned"
                counts[asp][bucket] += 1
            if r["sentiment"] == "negative" and asp in counts:
                negative_snippets[asp].append(snippet)

    # Build breakdown
    breakdown = []
    for asp in aspects:
        c = counts[asp]
        mentioned = c["positive"] + c["negative"]
        total_for_pct = total if total > 0 else 1
        breakdown.append({
            "aspect": asp,
            "positive_pct": round(c["positive"] / total_for_pct * 100, 1),
            "negative_pct": round(c["negative"] / total_for_pct * 100, 1),
            "not_mentioned_pct": round(c["not_mentioned"] / total_for_pct * 100, 1),
            "total_mentioned": mentioned,
        })

    # Build pain points — only aspects with at least 1 negative, sorted worst-first
    pain_points = []
    for asp in aspects:
        neg_count = counts[asp]["negative"]
        if neg_count == 0:
            continue
        quotes = negative_snippets[asp][:5]  # cap at 5 example quotes
        pain_points.append({
            "aspect": asp,
            "negative_count": neg_count,
            "example_quotes": quotes,
        })
    pain_points.sort(key=lambda x: x["negative_count"], reverse=True)

    # LLM summary
    llm_summary = None
    if include_llm_summary and total > 0:
        llm_summary = _generate_llm_summary(breakdown, pain_points, domain, total)

    return {
        "total_reviews": total,
        "domain": domain,
        "aspects": aspects,
        "breakdown": breakdown,
        "pain_points": pain_points,
        "llm_summary": llm_summary,
    }


def _generate_llm_summary(
    breakdown: list[dict],
    pain_points: list[dict],
    domain: str,
    total: int,
) -> str:
    client = _get_openai_client()

    breakdown_text = "\n".join(
        f"- {b['aspect']}: {b['positive_pct']}% positive, {b['negative_pct']}% negative"
        for b in breakdown
    )
    pain_text = "\n".join(
        f"- {p['aspect']}: {p['negative_count']} negative reviews. Examples: {'; '.join(p['example_quotes'][:2])}"
        for p in pain_points[:5]
    ) or "None"

    prompt = f"""You are a business analyst summarizing customer feedback for a {domain}.
You analyzed {total} reviews. Here is the sentiment breakdown per aspect:

{breakdown_text}

Top pain points (most negative feedback):
{pain_text}

Write a concise 3-5 sentence executive summary of:
1. What customers are happiest about
2. The biggest pain points and what customers say
3. One actionable recommendation

Be direct and specific. Do not use bullet points."""

    resp = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        max_tokens=300,
    )
    return resp.choices[0].message.content.strip()
