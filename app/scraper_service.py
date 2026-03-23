"""
Service layer for scraping movie reviews.
"""
import re


def extract_movie_id(imdb_url: str) -> str:
    """Extract IMDB title ID (e.g. 'tt1375666') from a URL."""
    match = re.search(r"(tt\d+)", imdb_url)
    if not match:
        raise ValueError(
            f"Invalid IMDB URL: could not find a title ID (tt...) in '{imdb_url}'"
        )
    return match.group(1)


def scrape_imdb_reviews(
    movie_id: str,
    max_reviews: int = 100,
) -> list[dict]:
    """
    Scrape IMDB reviews for a movie using Playwright (headless Chromium).

    Returns a list of review dicts with keys:
        movie_id, movie_title, review_text, rating, review_date, source
    """
    from app.imdb_playwright import scrape_imdb_reviews_playwright
    return scrape_imdb_reviews_playwright(movie_id, max_reviews)
