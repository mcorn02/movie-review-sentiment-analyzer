"""
Service layer for running the IMDB Scrapy spider in a subprocess.

Scrapy uses Twisted's reactor which can only start once per process,
so we isolate it in a subprocess to avoid conflicts with FastAPI's event loop.
"""
import json
import os
import re
import subprocess
import sys
import tempfile


def extract_movie_id(imdb_url: str) -> str:
    """
    Extract the IMDB movie ID (e.g. 'tt1375666') from a URL.

    Raises ValueError if the URL doesn't contain a valid IMDB title ID.
    """
    match = re.search(r"(tt\d+)", imdb_url)
    if not match:
        raise ValueError(
            f"Invalid IMDB URL: could not find a title ID (tt...) in '{imdb_url}'"
        )
    return match.group(1)


def scrape_imdb_reviews(
    movie_id: str,
    max_reviews: int = 75,
) -> list[dict]:
    """
    Scrape IMDB reviews for a movie by running the Scrapy spider
    in a subprocess.

    Returns a list of review dicts with keys:
        movie_id, movie_title, review_text, rating, review_date, source
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        output_file = os.path.join(tmpdir, "reviews.json")

        # Build the subprocess script that runs the spider
        script = f"""
import json, sys, os
sys.path.insert(0, {repr(os.getcwd())})
from scrapy.crawler import CrawlerProcess
from app.imdb_scraper import IMDBReviewSpider

output_file = {repr(output_file)}

settings = {{
    "FEEDS": {{
        output_file: {{
            "format": "json",
            "encoding": "utf8",
            "overwrite": True,
        }},
    }},
    "AUTOTHROTTLE_ENABLED": True,
    "AUTOTHROTTLE_TARGET_CONCURRENCY": 2.0,
    "DOWNLOAD_DELAY": 0.3,
    "USER_AGENT": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "HTTPERROR_ALLOWED_CODES": [403, 404],
    "LOG_LEVEL": "WARNING",
    "REQUEST_FINGERPRINTER_IMPLEMENTATION": "2.7",
}}

process = CrawlerProcess(settings=settings)
process.crawl(
    IMDBReviewSpider,
    movie_id_list=[{repr(movie_id)}],
    max_reviews={max_reviews},
)
process.start()
"""

        result = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            timeout=120,
        )

        if result.returncode != 0:
            stderr = result.stderr.strip()
            if "403" in stderr:
                raise RuntimeError(
                    f"IMDB returned 403 Forbidden for movie {movie_id}. "
                    "The site may be rate-limiting requests."
                )
            raise RuntimeError(
                f"Scraper subprocess failed (exit {result.returncode}): "
                f"{stderr[:500]}"
            )

        if not os.path.exists(output_file):
            return []

        with open(output_file, "r", encoding="utf-8") as f:
            content = f.read().strip()
            if not content:
                return []
            reviews = json.loads(content)

        return reviews
