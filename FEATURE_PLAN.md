# IMDB Review Scraping & Analysis Feature Plan

## Overview

This document outlines a comprehensive feature to scrape IMDB movie reviews, perform aspect-based sentiment analysis, and generate reports with visualizations - all in one integrated workflow.

## Workflow

### 1. **Movie Title Input**
- User provides a movie title (e.g., "The Matrix")
- Optionally search IMDB to find the exact movie if there are multiple matches
- Validate movie exists on IMDB

### 2. **Web Scraping Phase**
- Scrape IMDB reviews for the movie
- Extract:
  - Review text
  - Ratings (if available)
  - Review dates
  - Reviewer information
- Handle pagination to get multiple reviews (e.g., 50-100 reviews)
- Store reviews in structured format (list of dictionaries)

### 3. **Sentiment Analysis Phase**
- Process each review through existing aspect sentiment analysis
- Run both methods (LLM and NLI) or let user choose
- Aggregate results across all reviews
- Calculate statistics:
  - Percentage positive/negative/neutral per aspect
  - Average confidence scores
  - Most common sentiments

### 4. **Report Generation Phase**
- Create summary statistics:
  - Overall sentiment distribution per aspect
  - Average confidence scores
  - Review count analyzed
  - Movie metadata (title, year, etc.)
- Generate text summary highlighting key findings
- Format: HTML, PDF, or Markdown

### 5. **Visualization Phase**
- Create charts showing:
  - Sentiment distribution (bar charts per aspect)
  - Confidence scores distribution
  - Comparison between aspects (side-by-side)
  - Optional: Sentiment over time if dates available
- Interactive charts (using Plotly) embedded in Gradio interface

### 6. **Output**
- Display interactive dashboard (Gradio web interface)
- Export report as PDF/HTML
- Save data as CSV/JSON for further analysis

## Recommended Tools

### Web Scraping
- **BeautifulSoup4 + requests** - Simple, reliable for IMDB scraping
- **Scrapy** - More powerful framework, better for large-scale scraping
- **Selenium/Playwright** - If JavaScript rendering needed (IMDB usually doesn't require this)

### Data Processing
- **pandas** - Already in use, perfect for aggregating results
- **numpy** - Statistical calculations

### Visualization
- **matplotlib** - Basic charts
- **seaborn** - Statistical visualizations
- **plotly** - Interactive charts (works great with Gradio)
- **gradio** - Can embed visualizations in web interface

### Report Generation
- **ReportLab** - PDF generation
- **Jinja2** - HTML template rendering
- **markdown** - Text-based reports

## Technical Considerations

1. **Rate Limiting**: Add delays between requests to respect IMDB's servers
2. **Error Handling**: Handle missing reviews, network errors, parsing failures gracefully
3. **Caching**: Cache scraped reviews to avoid re-scraping same movies
4. **Legal/Ethical**: Respect robots.txt and terms of service
5. **User Experience**: Show progress during scraping and analysis (progress bars)

## Example Workflow in Code

```python
# Pseudo-code workflow
1. movie_title = input("Enter movie title: ")
2. reviews = scrape_imdb_reviews(movie_title, max_reviews=100)
3. results = []
   for review in reviews:
       sentiment = analyze(review.text, aspects, method)
       results.append(sentiment)
4. aggregated = aggregate_results(results)
5. report = generate_report(aggregated, movie_title)
6. charts = create_visualizations(aggregated)
7. display_dashboard(report, charts)
8. export_results(report, charts, format='html')
```

## Implementation Structure

### New Modules to Create

1. **`imdb_scraper.py`**
   - `search_movie(title)` - Find movie on IMDB
   - `scrape_reviews(movie_url, max_reviews)` - Scrape reviews
   - `parse_review_element(element)` - Extract review data
   - Rate limiting and error handling

2. **`aggregator.py`**
   - `aggregate_sentiment_results(results)` - Combine multiple analysis results
   - `calculate_statistics(aggregated)` - Compute percentages, averages
   - `generate_summary(statistics)` - Create text summary

3. **`visualizer.py`**
   - `create_sentiment_charts(aggregated)` - Generate Plotly charts
   - `create_confidence_charts(aggregated)` - Confidence score visualizations
   - `create_comparison_charts(aggregated)` - Aspect comparison charts

4. **`report_generator.py`**
   - `generate_html_report(data, charts)` - HTML report with embedded charts
   - `generate_pdf_report(data, charts)` - PDF export
   - `generate_markdown_report(data)` - Markdown format

5. **Enhanced `main.py`**
   - New CLI arguments: `--movie`, `--scrape`, `--max-reviews`
   - New Gradio interface with movie input and visualization display
   - Integration of all modules

## Dependencies to Add

```txt
beautifulsoup4>=4.12.0
requests>=2.31.0
plotly>=5.17.0
reportlab>=4.0.0
jinja2>=3.1.0
```

## User Interface Flow

### CLI Mode
```bash
# Scrape and analyze IMDB reviews
python main.py --movie "The Matrix" --scrape --max-reviews 50 --method "LLM (OpenAI)"

# With export
python main.py --movie "The Matrix" --scrape --export html
```

### Web Interface (Gradio)
1. User enters movie title
2. Clicks "Scrape & Analyze" button
3. Progress bar shows scraping progress
4. Progress bar shows analysis progress
5. Results displayed:
   - Summary statistics
   - Interactive charts
   - Download buttons for report export

## Data Structure

### Scraped Review
```python
{
    "text": "Review text here...",
    "rating": 8,  # Optional
    "date": "2024-01-15",  # Optional
    "reviewer": "username",  # Optional
    "source": "imdb"
}
```

### Aggregated Results
```python
{
    "movie_title": "The Matrix",
    "total_reviews": 50,
    "aspects": {
        "acting": {
            "positive": 35,
            "negative": 10,
            "neutral": 5,
            "not_mentioned": 0,
            "avg_confidence": 0.85
        },
        # ... other aspects
    },
    "overall_sentiment": {...}
}
```

## Future Enhancements

1. **Multiple Sources**: Scrape from Rotten Tomatoes, Metacritic, etc.
2. **Comparison**: Compare sentiment across different movies
3. **Time Series**: Track sentiment changes over time
4. **Review Filtering**: Filter by rating, date, length
5. **Batch Processing**: Analyze multiple movies at once
6. **Database Storage**: Store results in database for historical tracking
7. **API Endpoint**: REST API for programmatic access

## Implementation Priority

### Phase 1 (Core Features)
1. IMDB scraping module
2. Batch analysis integration
3. Basic aggregation and statistics
4. Simple visualization (bar charts)

### Phase 2 (Enhanced Features)
1. Report generation (HTML)
2. Enhanced Gradio interface with charts
3. Export functionality

### Phase 3 (Advanced Features)
1. PDF report generation
2. Multiple source scraping
3. Time series analysis
4. Database integration

## Questions to Consider

1. How many reviews should be scraped by default? (50? 100? 200?)
2. Should we cache scraped reviews locally?
3. What format should the report be? (HTML, PDF, both?)
4. Should we support multiple movie comparison?
5. Do we need to handle different languages?

