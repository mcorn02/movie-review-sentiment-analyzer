"""
Script to run IMDB review scraping using Scrapy.
"""
import logging
import os
from scrapy.crawler import CrawlerProcess
from .imdb_scraper import IMDBReviewSpider

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

DYNAMIC_MOVIE_IDS = ["tt30144839"]
MAX_REVIEWS = 100  # Maximum number of reviews to scrape per movie

# Get absolute path to ensure file is written in the correct location
base_dir = os.path.dirname(os.path.abspath(__file__))
output_file = os.path.join(base_dir, "movie_details.json")

process_settings = {
    # This is the key setting for output - use absolute path
    "FEEDS": {
        output_file: {
            "format": "json",
            "encoding": "utf8",
            "overwrite": True,
            "indent": 2,  # Pretty print JSON
        },
    },
    # Ensure items are properly exported
    "ITEM_PIPELINES": {},
    # Enable AutoThrottle
    "AUTOTHROTTLE_ENABLED": True,
    # Target an average of 1 concurrent request to the site
    "AUTOTHROTTLE_TARGET_CONCURRENCY": 1.0, 
    # Set a minimum floor for the delay (AutoThrottle will not go below this)
    "DOWNLOAD_DELAY": 0.5, 
    # For debugging and seeing the adjustments in real time (optional)
    "AUTOTHROTTLE_DEBUG": False,
    # Set default user agent (backup in case headers aren't set)
    "USER_AGENT": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    # Handle HTTP errors properly
    "HTTPERROR_ALLOWED_CODES": [403, 404],
}

process = CrawlerProcess(settings=process_settings)

process.crawl(IMDBReviewSpider, movie_id_list=DYNAMIC_MOVIE_IDS, max_reviews=MAX_REVIEWS)

logger.info("Starting Scrapy IMDB Crawl")
logger.info(f"Output will be written to: {output_file}")
process.start()
logger.info("Scrapy CrawlerProcess finished")


