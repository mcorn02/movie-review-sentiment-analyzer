from playwright.sync_api import sync_playwright


def scrape_imdb_reviews_playwright(movie_id: str, max_reviews: int = 75) -> list[dict]:
    url = f"https://www.imdb.com/title/{movie_id}/reviews/"
    reviews = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=[
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
        ])
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            locale="en-US",
        )
        page = context.new_page()
        # Hide webdriver flag
        page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

        page.goto(url, wait_until="domcontentloaded", timeout=60000)

        # Wait for WAF challenge to resolve (page may reload after JS token)
        # then wait for review content to appear
        try:
            page.wait_for_selector(
                'div.ipc-html-content-inner-div, div.text.show-more__control, article',
                timeout=30000
            )
        except Exception:
            # WAF may have reloaded the page — wait and try again
            page.wait_for_timeout(5000)
            try:
                page.wait_for_selector(
                    'div.ipc-html-content-inner-div, div.text.show-more__control, article',
                    timeout=15000
                )
            except Exception:
                pass  # Proceed anyway and try to extract whatever is there

        # Extract movie title
        raw_title = page.title()
        movie_title = raw_title.replace(" - User reviews", "").replace(" - User Reviews - IMDb", "").replace(" - IMDb", "").strip()

        # Try to load more reviews if button exists
        for _ in range(3):  # up to 3 load-more clicks
            if len(reviews) >= max_reviews:
                break
            try:
                btn = page.query_selector('button.ipc-btn--see-more, [data-testid="load-more-btn"]')
                if btn:
                    btn.click()
                    page.wait_for_timeout(1500)
            except Exception:
                break

        # Extract review containers
        containers = (
            page.query_selector_all('article.user-review-item') or
            page.query_selector_all('div[data-testid="review-card"]') or
            page.query_selector_all('div.lister-item-content') or
            page.query_selector_all('article')
        )

        for container in containers[:max_reviews]:
            # Review text
            text_el = (
                container.query_selector('div.ipc-html-content-inner-div') or
                container.query_selector('div.text.show-more__control') or
                container.query_selector('div.content div.text')
            )
            review_text = text_el.inner_text().strip() if text_el else None

            if not review_text or len(review_text) < 20:
                continue

            # Rating
            rating_el = container.query_selector('span.ipc-rating-star--rating, span.rating-other-user-rating span')
            rating = None
            if rating_el:
                try:
                    rating = int(rating_el.inner_text().strip())
                except Exception:
                    pass

            # Date
            date_el = container.query_selector('span.review-date, li.review-date')
            review_date = date_el.inner_text().strip() if date_el else None

            reviews.append({
                'movie_id': movie_id,
                'movie_title': movie_title,
                'review_text': review_text,
                'rating': rating,
                'review_date': review_date,
                'source': 'imdb',
            })

        browser.close()

    return reviews
