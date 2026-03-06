"""
Pydantic request/response models for the API.
"""
from __future__ import annotations
from enum import Enum
from typing import Any
from pydantic import BaseModel, Field


class AnalysisMethod(str, Enum):
    llm = "LLM (OpenAI)"
    nli = "Zero-shot NLI (local)"


# ── Domain config ─────────────────────────────────────────────────────────────

class DomainCreate(BaseModel):
    name: str = Field(..., description="Human-readable domain name, e.g. 'restaurant'")
    aspects: list[str] = Field(..., description="Aspects to analyze for this domain")
    description: str | None = Field(None, description="Optional context shown to the LLM")


class DomainResponse(DomainCreate):
    id: str
    is_preset: bool


# ── Single review ─────────────────────────────────────────────────────────────

class AnalyzeRequest(BaseModel):
    review: str
    domain_id: str | None = Field(None, description="Use a saved domain config by ID")
    domain: str = Field("product", description="Domain label if not using a saved config")
    aspects: list[str] | None = Field(None, description="Override aspects from domain config")
    method: AnalysisMethod = AnalysisMethod.llm


class AspectResult(BaseModel):
    aspect: str
    sentiment: str  # positive | negative | not_mentioned


class AnalyzeResponse(BaseModel):
    domain: str
    aspects: list[str]
    method: str
    results: list[AspectResult]


# ── Batch job ─────────────────────────────────────────────────────────────────

class JobStatus(str, Enum):
    queued = "queued"
    running = "running"
    done = "done"
    failed = "failed"


class JobSubmitResponse(BaseModel):
    job_id: str
    status: JobStatus
    message: str


class AspectBreakdown(BaseModel):
    aspect: str
    positive_pct: float
    negative_pct: float
    not_mentioned_pct: float
    total_mentioned: int


class PainPoint(BaseModel):
    aspect: str
    negative_count: int
    example_quotes: list[str]


class Report(BaseModel):
    total_reviews: int
    domain: str
    aspects: list[str]
    breakdown: list[AspectBreakdown]
    pain_points: list[PainPoint]  # sorted worst-first
    llm_summary: str | None = None  # natural-language summary from LLM


class ReviewPrediction(BaseModel):
    review_index: int
    review_snippet: str  # first 120 chars
    results: list[AspectResult]


class JobStatusResponse(BaseModel):
    job_id: str
    status: JobStatus
    progress: str | None = None   # e.g. "12/50 reviews"
    error: str | None = None
    predictions: list[ReviewPrediction] | None = None
    report: Report | None = None
    created_at: str
    completed_at: str | None = None
