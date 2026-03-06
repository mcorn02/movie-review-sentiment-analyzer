"""
Single-review analysis endpoint.
"""
from fastapi import APIRouter, HTTPException

from api.db import get_domain
from api.models import AnalyzeRequest, AnalyzeResponse, AspectResult
from app.config import DEFAULT_ASPECTS
from app.sentiment_analyzer import analyze

router = APIRouter(prefix="/analyze", tags=["analyze"])


@router.post("", response_model=AnalyzeResponse)
def analyze_review(body: AnalyzeRequest):
    """Analyze a single review synchronously."""
    # Resolve domain + aspects
    domain_label = body.domain
    aspects = body.aspects

    if body.domain_id:
        domain_cfg = get_domain(body.domain_id)
        if not domain_cfg:
            raise HTTPException(status_code=404, detail=f"Domain '{body.domain_id}' not found")
        domain_label = domain_cfg["name"]
        if aspects is None:
            aspects = domain_cfg["aspects"]

    if not aspects:
        aspects = DEFAULT_ASPECTS

    df = analyze(body.review, aspects, body.method.value, domain=domain_label)

    # Convert DataFrame to response model
    results = [
        AspectResult(aspect=row["aspect"], sentiment=row["sentiment"])
        for _, row in df.iterrows()
        if row["aspect"] not in ("", "(error)")
    ]

    if df["aspect"].iloc[0] == "(error)":
        raise HTTPException(status_code=500, detail=df["sentiment"].iloc[0])

    return AnalyzeResponse(
        domain=domain_label,
        aspects=aspects,
        method=body.method.value,
        results=results,
    )
