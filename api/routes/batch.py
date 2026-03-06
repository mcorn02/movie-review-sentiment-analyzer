"""
Batch analysis endpoints: file upload + async job polling.
"""
from __future__ import annotations
import io
import uuid
from datetime import datetime, timezone

import pandas as pd
from fastapi import APIRouter, BackgroundTasks, HTTPException, UploadFile, File, Form
from fastapi.responses import JSONResponse

from api.db import get_domain, insert_job, update_job_progress, complete_job, fail_job, get_job
from api.models import (
    AnalysisMethod,
    JobSubmitResponse,
    JobStatus,
    JobStatusResponse,
    ReviewPrediction,
    AspectResult,
)
from api.report import build_report
from app.config import DEFAULT_ASPECTS
from app.sentiment_analyzer import analyze

router = APIRouter(tags=["batch"])

_SNIPPET_LEN = 120


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _detect_review_column(df: pd.DataFrame, hint: str | None) -> str:
    """Return the column name containing review text."""
    if hint and hint in df.columns:
        return hint
    # Common column name candidates in priority order
    candidates = ["review", "text", "comment", "body", "content", "description", "feedback"]
    for c in candidates:
        if c in df.columns:
            return c
        if c in [col.lower() for col in df.columns]:
            return next(col for col in df.columns if col.lower() == c)
    # Fall back to the first string column
    for col in df.columns:
        if df[col].dtype == object:
            return col
    raise ValueError(
        f"Could not detect a review text column. Available columns: {list(df.columns)}. "
        "Pass 'review_column' to specify one."
    )


def _run_batch_job(
    job_id: str,
    reviews: list[str],
    domain_label: str,
    aspects: list[str],
    method: str,
) -> None:
    """Background task: process all reviews, write results to DB."""
    predictions = []
    try:
        for i, review in enumerate(reviews):
            df = analyze(review, aspects, method, domain=domain_label)

            results = [
                {"aspect": row["aspect"], "sentiment": row["sentiment"]}
                for _, row in df.iterrows()
                if row["aspect"] not in ("", "(error)")
            ]

            predictions.append({
                "review_index": i,
                "review_snippet": review[:_SNIPPET_LEN],
                "results": results,
            })

            # Checkpoint progress every 10 reviews
            if (i + 1) % 10 == 0:
                update_job_progress(job_id, i + 1)

        report = build_report(predictions, domain_label, aspects, include_llm_summary=True)
        complete_job(job_id, predictions, report, _now())

    except Exception as exc:
        fail_job(job_id, str(exc), _now())


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/analyze/batch", response_model=JobSubmitResponse, status_code=202)
async def submit_batch(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="CSV file containing reviews"),
    domain_id: str | None = Form(None, description="Saved domain config ID"),
    domain: str = Form("product", description="Domain label if not using a saved config"),
    aspects: str | None = Form(None, description="Comma-separated aspects to override domain config"),
    method: AnalysisMethod = Form(AnalysisMethod.llm),
    review_column: str | None = Form(None, description="CSV column name containing review text"),
):
    """Upload a CSV of reviews. Returns a job_id to poll for results."""
    # Read CSV
    contents = await file.read()
    try:
        df = pd.read_csv(io.BytesIO(contents), encoding="utf-8", on_bad_lines="skip")
    except Exception:
        try:
            df = pd.read_csv(io.BytesIO(contents), encoding="latin-1", on_bad_lines="skip")
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Could not parse CSV: {e}")

    if df.empty:
        raise HTTPException(status_code=400, detail="Uploaded CSV is empty")

    # Detect review column
    try:
        col = _detect_review_column(df, review_column)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    reviews = df[col].dropna().astype(str).tolist()
    if not reviews:
        raise HTTPException(status_code=400, detail="No review text found in the detected column")

    # Resolve domain
    domain_label = domain
    resolved_aspects = [a.strip() for a in aspects.split(",")] if aspects else None

    if domain_id:
        domain_cfg = get_domain(domain_id)
        if not domain_cfg:
            raise HTTPException(status_code=404, detail=f"Domain '{domain_id}' not found")
        domain_label = domain_cfg["name"]
        if resolved_aspects is None:
            resolved_aspects = domain_cfg["aspects"]

    if not resolved_aspects:
        resolved_aspects = DEFAULT_ASPECTS

    # Create job
    job_id = str(uuid.uuid4())
    insert_job(job_id, domain_label, method.value, resolved_aspects, len(reviews), _now())

    # Queue background work
    background_tasks.add_task(
        _run_batch_job, job_id, reviews, domain_label, resolved_aspects, method.value
    )

    return JobSubmitResponse(
        job_id=job_id,
        status=JobStatus.queued,
        message=f"Job queued. {len(reviews)} reviews will be analyzed. Poll GET /jobs/{job_id} for results.",
    )


@router.get("/jobs/{job_id}", response_model=JobStatusResponse)
def get_job_status(job_id: str):
    """Poll for job status and results."""
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")

    progress = None
    if job["status"] in ("running", "queued") and job["total"]:
        progress = f"{job['completed']}/{job['total']} reviews"

    predictions_out = None
    if job["predictions"]:
        predictions_out = [
            ReviewPrediction(
                review_index=p["review_index"],
                review_snippet=p["review_snippet"],
                results=[AspectResult(**r) for r in p["results"]],
            )
            for p in job["predictions"]
        ]

    return JobStatusResponse(
        job_id=job_id,
        status=JobStatus(job["status"]),
        progress=progress,
        error=job.get("error"),
        predictions=predictions_out,
        report=job.get("report"),
        created_at=job["created_at"],
        completed_at=job.get("completed_at"),
    )
