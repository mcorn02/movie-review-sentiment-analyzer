"""
FastAPI application entrypoint.

Run with:
    uvicorn api.main:app --reload
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI

from api.db import init_db
from api.routes.analyze import router as analyze_router
from api.routes.batch import router as batch_router
from api.routes.domains import router as domains_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="Aspect Sentiment API",
    description="Domain-agnostic aspect-based sentiment analysis with batch processing and business reports.",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(analyze_router)
app.include_router(batch_router)
app.include_router(domains_router)


@app.get("/health", tags=["meta"])
def health():
    return {"status": "ok"}
