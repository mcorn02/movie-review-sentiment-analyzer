"""
SSE streaming endpoint for the movie report pipeline.

POST /report/imdb — accepts an IMDB URL, scrapes reviews,
runs analysis, and streams progress + results as Server-Sent Events.
"""
import asyncio
import json
import re

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from api.models import IMDBReportRequest
from app.config import DEFAULT_ASPECTS
from app.scraper_service import extract_movie_id, scrape_imdb_reviews
from app.report_generator import async_generate_report

router = APIRouter(prefix="/report", tags=["report"])

IMDB_URL_RE = re.compile(r"imdb\.com/title/tt\d+", re.I)


def _sse_event(event: str, data: dict) -> str:
    """Format a single SSE event."""
    payload = json.dumps(data)
    return f"event: {event}\ndata: {payload}\n\n"


@router.post("/imdb")
async def imdb_report(request: IMDBReportRequest):
    """
    Stream a movie report via SSE.

    Stages: scraping → analyzing → generating → done
    """
    if not IMDB_URL_RE.search(request.imdb_url):
        raise HTTPException(status_code=400, detail="Please enter a valid IMDB movie URL (imdb.com/title/tt...).")

    try:
        movie_id = extract_movie_id(request.imdb_url)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    aspects = request.aspects or DEFAULT_ASPECTS

    async def event_stream():
        # Stage 1: Scraping
        yield _sse_event("stage", {
            "stage": "scraping",
            "message": f"Scraping reviews from IMDB for {movie_id}...",
        })

        try:
            reviews_data = await asyncio.to_thread(scrape_imdb_reviews, movie_id, 75)
        except Exception as e:
            yield _sse_event("error", {"message": str(e)})
            yield _sse_event("done", {"status": "error"})
            return

        if not reviews_data:
            yield _sse_event("error", {
                "message": f"No reviews found for '{movie_id}' on IMDB.",
            })
            yield _sse_event("done", {"status": "error"})
            return

        review_texts = [r["review_text"] for r in reviews_data if r.get("review_text")]
        movie_title = reviews_data[0].get("movie_title", movie_id) if reviews_data else movie_id

        yield _sse_event("stage", {
            "stage": "scraping",
            "message": f"Scraped {len(review_texts)} reviews for '{movie_title}'",
            "progress": len(review_texts),
            "total": len(review_texts),
            "movie_title": movie_title,
        })

        if len(review_texts) < 10:
            yield _sse_event("warning", {
                "message": f"Only {len(review_texts)} reviews found — results may be less reliable.",
            })

        # Stage 2 & 3: Analysis + Report generation (via async pipeline)
        async def on_stage(stage, data=None):
            if stage == "analyzing":
                event_queue.put_nowait(("stage", {
                    "stage": "analyzing",
                    "message": f"Analyzing sentiment... ({data.get('progress', 0)}/{data.get('total', 0)})",
                    **data,
                }))
            elif stage == "generating":
                event_queue.put_nowait(("stage", {
                    "stage": "generating",
                    "message": data.get("message", "Generating report..."),
                }))
            elif stage == "aspect_complete":
                event_queue.put_nowait(("aspect_complete", data))

        event_queue = asyncio.Queue()

        async def run_report():
            try:
                report = await async_generate_report(
                    review_texts, aspects, on_stage=on_stage
                )
                event_queue.put_nowait(("_result", report))
            except Exception as e:
                event_queue.put_nowait(("error", {"message": str(e)}))
            finally:
                event_queue.put_nowait(("_done", None))

        task = asyncio.create_task(run_report())

        report_result = None
        while True:
            event_type, event_data = await event_queue.get()
            if event_type == "_done":
                break
            elif event_type == "_result":
                report_result = event_data
                continue
            yield _sse_event(event_type, event_data)

        await task

        if report_result is None:
            yield _sse_event("done", {"status": "error"})
            return

        # Send chart data
        distributions = []
        for ar in report_result["aspects"]:
            distributions.append({
                "aspect": ar["name"],
                "positive": ar["distribution"]["positive"]["count"],
                "negative": ar["distribution"]["negative"]["count"],
                "not_mentioned": ar["distribution"]["not_mentioned"]["count"],
                "positive_pct": ar["distribution"]["positive"]["pct"],
                "negative_pct": ar["distribution"]["negative"]["pct"],
                "not_mentioned_pct": ar["distribution"]["not_mentioned"]["pct"],
            })

        yield _sse_event("charts", {"distributions": distributions})

        yield _sse_event("report", {
            "overall_summary": report_result["overall_summary"],
            "movie_title": movie_title,
            "n_reviews": report_result["n_reviews"],
            "aspects": report_result["aspects"],
        })

        yield _sse_event("done", {"status": "complete"})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
