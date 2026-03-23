from playwright.sync_api import sync_playwright


def scrape_imdb_reviews_playwright(movie_id: str, max_reviews: int = 100) -> list[dict]:
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

        # Click load-more until we have enough review containers or button disappears
        # The button text matches "\d+ more" (e.g. "25 more")
        import re as _re
        for _ in range(20):  # up to 20 clicks (~25 reviews each = ~500 max)
            containers_so_far = page.query_selector_all('article.user-review-item')
            if len(containers_so_far) >= max_reviews:
                break
            try:
                load_more = page.locator('button', has_text=_re.compile(r'^\d+ more$'))
                if load_more.count() == 0:
                    break
                load_more.first.click()
                page.wait_for_timeout(2000)
            except Exception:
                break

        # Extract review containers
        containers = page.query_selector_all('article.user-review-item')

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
