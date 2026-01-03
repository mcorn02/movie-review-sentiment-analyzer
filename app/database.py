import sqlite3
from datetime import datetime
from pathlib import Path


def get_db_path():
    """Get the path to the SQLite database file."""
    base_dir = Path(__file__).parent
    return base_dir / "reviews.db"


def init_database():
    """Initialize the database and create tables if they don't exist."""
    db_path = get_db_path()
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    # Create movies table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS movies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            imdb_id TEXT UNIQUE NOT NULL,
            title TEXT,
            year INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Create index on imdb_id for faster lookups
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_movies_imdb_id ON movies(imdb_id)
    """)
    
    conn.commit()
    conn.close()


def get_or_create_movie(imdb_id, title=None, year=None):
    """
    Get existing movie by imdb_id or create a new one.
    
    Args:
        imdb_id: IMDB ID (e.g., "tt30144839")
        title: Movie title (optional)
        year: Release year (optional)
        
    Returns:
        tuple: (movie_id, created) where created is True if movie was just created
    """
    db_path = get_db_path()
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    # Try to get existing movie
    cursor.execute("SELECT id FROM movies WHERE imdb_id = ?", (imdb_id,))
    result = cursor.fetchone()
    
    if result:
        movie_id = result[0]
        # Update title/year if provided and different
        if title or year:
            cursor.execute("""
                UPDATE movies 
                SET title = COALESCE(?, title), 
                    year = COALESCE(?, year),
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (title, year, movie_id))
            conn.commit()
        conn.close()
        return movie_id, False
    else:
        # Create new movie
        cursor.execute("""
            INSERT INTO movies (imdb_id, title, year)
            VALUES (?, ?, ?)
        """, (imdb_id, title, year))
        movie_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return movie_id, True


def save_review(movie_id, review_text, rating=None, review_date=None, source="IMDB"):
    """
    Adds review to 
    """
    db_path = get_db_path()
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO reviews (movie_id, review_text, rating, review_date, source, scraped_at)
        VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
    """, (movie_id, review_text, rating, review_date, source))
    review_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return review_id

    