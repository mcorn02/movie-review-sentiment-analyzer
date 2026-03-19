"""
FastAPI application entrypoint.

Run with:
    uvicorn api.main:app --reload
"""
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from api.db import init_db
from api.routes.analyze import router as analyze_router
from api.routes.batch import router as batch_router
from api.routes.domains import router as domains_router
from api.routes.report import router as report_router

FRONTEND_DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="Aspect Sentiment API",
    description="Domain-agnostic aspect-based sentiment analysis with batch processing and business reports.",
    version="0.2.0",
    lifespan=lifespan,
)

# CORS — allow React dev server and any localhost origin
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API routes under /api prefix
app.include_router(analyze_router, prefix="/api")
app.include_router(batch_router, prefix="/api")
app.include_router(domains_router, prefix="/api")
app.include_router(report_router, prefix="/api")


@app.get("/api/health", tags=["meta"])
def health():
    return {"status": "ok"}


# Serve frontend static files in production
if FRONTEND_DIST.is_dir():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")

    @app.get("/{full_path:path}")
    async def serve_spa(request: Request, full_path: str):
        """SPA fallback: serve index.html for any non-API, non-static route."""
        # Check if the file exists in dist
        file_path = FRONTEND_DIST / full_path
        if file_path.is_file():
            return FileResponse(file_path)
        # Otherwise serve index.html for client-side routing
        return FileResponse(FRONTEND_DIST / "index.html")
