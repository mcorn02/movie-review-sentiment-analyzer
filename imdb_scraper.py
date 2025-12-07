import re
import scrapy
from scrapy.crawler import CrawlerProcess


class IMDBReviewSpider(scrapy.Spider):
    name = 'IMDB_review_spider'

    base_url = 'https://www.imdb.com/title/{id}/reviews/'

    def __init__(self, movie_id_list=None, max_reviews=50, *args, **kwargs):
        super(IMDBReviewSpider, self).__init__(*args, **kwargs)
        self.movie_ids = movie_id_list or []
        self.max_reviews = max_reviews
        self.reviews_collected = 0

        if not self.movie_ids:
            self.logger.warning("No movie IDs provided to the Spider.")

    def start_requests(self):
        '''
        Generates the initial request based on the dynamically provided list.
        '''
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        
        for movie_id in self.movie_ids:
            fullurl = self.base_url.format(id=movie_id)

            yield scrapy.Request(
                url=fullurl,
                callback=self.parse,
                meta={'movie_id': movie_id},
                headers=headers
            )

    def parse(self, response):
        movie_id = response.meta.get('movie_id')
        page_start = response.meta.get('start', 0)
        
        # Log response status
        self.logger.info(f"Parsing reviews page for Movie ID: {movie_id}, Status: {response.status}, Start: {page_start}")
        
        # Check if we got blocked
        if response.status == 403:
            self.logger.error(f"403 Forbidden - IMDB blocked the request for {movie_id}")
            return
        
        # Extract movie title from the page
        movie_title = (
            response.css('h3[itemprop="name"] a::text').get() or
            response.css('div.parent a::text').get() or
            response.xpath('//h3[@itemprop="name"]/a/text()').get()
        )
        if movie_title:
            movie_title = movie_title.strip()
        
        # Extract individual reviews - try multiple selectors
        # IMDB uses different structures, try the most common ones
        review_containers = response.css('div.lister-item-content')
        if not review_containers:
            # Try article elements that contain ipc-list-card (newer IMDB layout)
            # This is more specific than just 'article' to avoid matching other page articles
            review_containers = response.xpath('//article[.//div[contains(@class, "ipc-list-card")]]')
        if not review_containers:
            # Try article elements (newer IMDB layout uses article tags)
            review_containers = response.css('article')
        if not review_containers:
            # Try ipc-list-card pattern (based on discovered selector structure)
            review_containers = response.css('div.ipc-list-card')
        if not review_containers:
            # Try alternative selector for newer IMDB layout
            review_containers = response.css('div.ipc-html-content-inner-div')
        if not review_containers:
            # Try another alternative
            review_containers = response.css('div[data-testid="review-container"]')
        if not review_containers:
            # Try class-based selector
            review_containers = response.css('div.review-container')
        if not review_containers:
            # Last resort: any div with review-related classes
            review_containers = response.xpath('//div[contains(@class, "review") or contains(@class, "lister")]')
        
        self.logger.info(f"Found {len(review_containers)} review containers on page")
        
        # Debug: log a sample of the HTML structure if no containers found
        if not review_containers:
            self.logger.warning("No review containers found. Sample HTML structure:")
            sample_html = response.css('body').get()[:500] if response.css('body').get() else "No body found"
            self.logger.warning(f"First 500 chars of body: {sample_html}")
        elif len(review_containers) > 0:
            # Debug first container structure
            first_html = review_containers[0].get()[:400] if review_containers[0].get() else "No HTML"
            self.logger.debug(f"First container HTML sample: {first_html[:400]}")
        
        for idx, review_container in enumerate(review_containers):
            # Check if we've reached the max reviews limit
            if self.reviews_collected >= self.max_reviews:
                self.logger.info(f"Reached max reviews limit ({self.max_reviews})")
                return
            
            # Extract rating (if available) - try multiple selectors
            rating = None
            rating_element = (
                review_container.css('span.rating-other-user-rating span::text').get() or
                review_container.css('div.ipc-list-card__content span::text').get() or
                review_container.css('div.ipc-list-card__content > div > span::text').get() or
                review_container.css('span[class*="rating"]::text').get() or
                review_container.xpath('.//div[@class="ipc-list-card__content"]//span/text()').get() or
                review_container.xpath('.//span[contains(@class, "rating")]/text()').get()
            )
            if rating_element:
                try:
                    # Extract just the number
                    rating_match = re.search(r'\d+', str(rating_element))
                    if rating_match:
                        rating = int(rating_match.group())
                except (ValueError, AttributeError):
                    pass
            
            # Extract review title - try multiple selectors
            review_title = (
                review_container.css('a.title::text').get() or
                review_container.css('h2 a::text').get() or
                review_container.xpath('.//a[contains(@class, "title")]/text()').get()
            )
            if review_title:
                review_title = review_title.strip()
            
            # Extract review text - try multiple selectors
            review_text = None
            # Try the main selector first (IMDB's standard structure)
            review_text_parts = review_container.css('div.text.show-more__control::text').getall()
            if review_text_parts:
                review_text = ' '.join([t.strip() for t in review_text_parts if t.strip()])
            
            # Try ipc-list-card__content structure (newer IMDB layout)
            if not review_text:
                review_text_parts = review_container.css('div.ipc-list-card__content div::text').getall()
                if review_text_parts:
                    # Filter out very short text (likely UI elements, not review text)
                    filtered_parts = [t.strip() for t in review_text_parts if t.strip() and len(t.strip()) > 20]
                    if filtered_parts:
                        review_text = ' '.join(filtered_parts)
            
            # Try XPath for ipc-list-card__content structure
            if not review_text:
                review_text_parts = review_container.xpath('.//div[@class="ipc-list-card__content"]//text()').getall()
                if review_text_parts:
                    # Filter out very short text and join
                    filtered_parts = [t.strip() for t in review_text_parts if t.strip() and len(t.strip()) > 20]
                    if filtered_parts:
                        review_text = ' '.join(filtered_parts)
            
            # If that didn't work, try alternative selectors
            if not review_text:
                review_text_parts = review_container.css('div.content div.text::text').getall()
                if review_text_parts:
                    review_text = ' '.join([t.strip() for t in review_text_parts if t.strip()])
            
            # Try XPath as fallback
            if not review_text:
                review_text_parts = review_container.xpath('.//div[contains(@class, "text")]//text()').getall()
                if review_text_parts:
                    review_text = ' '.join([t.strip() for t in review_text_parts if t.strip()])
            
            # Last resort: get all text from the container, excluding known non-review elements
            if not review_text:
                all_text = review_container.xpath('.//text()').getall()
                # Filter out empty strings and very short strings (likely navigation/UI elements)
                filtered_text = [t.strip() for t in all_text if t.strip() and len(t.strip()) > 10]
                if filtered_text:
                    # Take the longest text block as the review (usually the review text is the longest)
                    review_text = max(filtered_text, key=len) if filtered_text else None
            
            if review_text:
                review_text = review_text.strip()
            
            # Extract reviewer name - try multiple selectors
            reviewer = (
                review_container.css('span.display-name-link a::text').get() or
                review_container.css('span[class*="display-name"] a::text').get() or
                review_container.xpath('.//span[contains(@class, "name")]//a/text()').get()
            )
            if reviewer:
                reviewer = reviewer.strip()
            
            # Extract review date - try multiple selectors
            review_date = (
                review_container.css('span.review-date::text').get() or
                review_container.css('span[class*="date"]::text').get() or
                review_container.xpath('.//span[contains(@class, "date")]/text()').get()
            )
            if review_date:
                review_date = review_date.strip()
            
            # Debug first few reviews (after all extractions)
            if idx < 2:
                self.logger.debug(f"Review {idx}: text_length={len(review_text) if review_text else 0}, rating={rating}, reviewer={reviewer}, has_text={bool(review_text)}")
            
            # Only yield if we have review text
            if review_text and len(review_text.strip()) > 0:
                self.reviews_collected += 1
                review_item = {
                    'movie_id': movie_id,
                    'movie_title': movie_title,
                    'review_title': review_title,
                    'review_text': review_text,
                    'rating': rating,
                    'reviewer': reviewer,
                    'review_date': review_date,
                    'source': 'imdb'
                }
                self.logger.info(f"Yielding review {self.reviews_collected}/{self.max_reviews} - Rating: {rating}, Reviewer: {reviewer}, Text length: {len(review_text)}")
                yield review_item
            else:
                if idx < 3:
                    self.logger.warning(f"Review {idx} skipped - no valid review text found (text was: {repr(review_text[:50]) if review_text else None})")
        
        # Handle pagination - look for "Load More" button or next page link
        if self.reviews_collected < self.max_reviews:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Referer': response.url,
            }
            
            # Try to find the "Load More" button or pagination
            load_more_data = response.css('div.load-more-data::attr(data-key)').get()
            if load_more_data:
                # IMDB uses AJAX pagination, construct the URL
                next_start = page_start + len(review_containers)
                next_url = f"{self.base_url.format(id=movie_id)}?start={next_start}"
                
                yield scrapy.Request(
                    url=next_url,
                    callback=self.parse,
                    meta={'movie_id': movie_id, 'start': next_start},
                    headers=headers
                )
            else:
                # Try alternative pagination method
                next_page = response.css('a.load-more-data::attr(href)').get()
                if next_page:
                    next_url = response.urljoin(next_page)
                    yield scrapy.Request(
                        url=next_url,
                        callback=self.parse,
                        meta={'movie_id': movie_id, 'start': page_start + len(review_containers)},
                        headers=headers
                    )
