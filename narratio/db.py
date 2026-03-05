"""SQLite database initialization and helpers."""

import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS articles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id TEXT UNIQUE NOT NULL,
    headline TEXT NOT NULL,
    summary TEXT,
    source TEXT,
    url TEXT,
    published_at TEXT NOT NULL,
    keywords TEXT,
    category TEXT,
    news_desk TEXT,
    word_count INTEGER,
    ingested_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS article_analysis (
    article_id INTEGER PRIMARY KEY REFERENCES articles(id),
    embedding_index INTEGER,
    sentiment_score REAL,
    sentiment_label TEXT,
    cluster_id INTEGER,
    merged_cluster_id INTEGER,
    is_relevant BOOLEAN DEFAULT 1,
    narrative_id INTEGER REFERENCES narratives(id)
);

CREATE TABLE IF NOT EXISTS narratives (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    label TEXT NOT NULL,
    first_seen TEXT NOT NULL,
    last_seen TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    centroid_embedding_index INTEGER,
    significance_score REAL
);

CREATE TABLE IF NOT EXISTS narrative_weeks (
    narrative_id INTEGER NOT NULL REFERENCES narratives(id),
    week_start TEXT NOT NULL,
    article_count INTEGER NOT NULL DEFAULT 0,
    share_of_attention REAL,
    z_score REAL,
    sentiment_mean REAL,
    summary TEXT,
    top_headline_ids TEXT,
    PRIMARY KEY (narrative_id, week_start)
);

CREATE TABLE IF NOT EXISTS weekly_totals (
    week_start TEXT PRIMARY KEY,
    total_articles INTEGER NOT NULL DEFAULT 0,
    total_clustered INTEGER NOT NULL DEFAULT 0,
    total_noise INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS economist_covers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL UNIQUE,
    title TEXT,
    image_url TEXT NOT NULL,
    edition_url TEXT,
    year INTEGER NOT NULL,
    scraped_at TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_covers_year ON economist_covers(year);
CREATE INDEX IF NOT EXISTS idx_covers_date ON economist_covers(date DESC);

-- article_analysis indexes (most critical — queried in cluster, label, sentiment, data, summarize)
CREATE INDEX IF NOT EXISTS idx_aa_narrative_id ON article_analysis(narrative_id);
CREATE INDEX IF NOT EXISTS idx_aa_embedding_index ON article_analysis(embedding_index);
CREATE INDEX IF NOT EXISTS idx_aa_is_relevant ON article_analysis(is_relevant);
CREATE INDEX IF NOT EXISTS idx_aa_cluster_id ON article_analysis(cluster_id);
CREATE INDEX IF NOT EXISTS idx_aa_merged_cluster ON article_analysis(merged_cluster_id);

-- articles indexes
CREATE INDEX IF NOT EXISTS idx_articles_published ON articles(published_at DESC);
CREATE INDEX IF NOT EXISTS idx_articles_source ON articles(source);

-- narrative_weeks indexes (critical for timeline/reporting)
CREATE INDEX IF NOT EXISTS idx_nw_lookup ON narrative_weeks(narrative_id, week_start);
CREATE INDEX IF NOT EXISTS idx_nw_week ON narrative_weeks(week_start DESC);

-- narratives indexes
CREATE INDEX IF NOT EXISTS idx_narratives_status ON narratives(status);
"""


def init_db(db_path: str) -> None:
    """Create database and tables if they don't exist."""
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.executescript(SCHEMA)
    _migrate(conn)
    conn.close()


def _migrate(conn: sqlite3.Connection) -> None:
    """Migrate old schema variants to current schema."""
    cols = [row[1] for row in conn.execute("PRAGMA table_info(articles)").fetchall()]
    if "nyt_id" in cols and "source_id" not in cols:
        conn.execute("ALTER TABLE articles RENAME COLUMN nyt_id TO source_id")
        conn.commit()
    if "finnhub_id" in cols and "source_id" not in cols:
        conn.execute("ALTER TABLE articles RENAME COLUMN finnhub_id TO source_id")
        conn.commit()

    # Add significance_score to narratives if missing
    narr_cols = [row[1] for row in conn.execute("PRAGMA table_info(narratives)").fetchall()]
    if "significance_score" not in narr_cols:
        conn.execute("ALTER TABLE narratives ADD COLUMN significance_score REAL")
        conn.commit()

    # Add is_relevant and merged_cluster_id to article_analysis if missing
    aa_cols = [row[1] for row in conn.execute("PRAGMA table_info(article_analysis)").fetchall()]
    if "is_relevant" not in aa_cols:
        conn.execute("ALTER TABLE article_analysis ADD COLUMN is_relevant BOOLEAN DEFAULT 1")
        conn.commit()
    if "merged_cluster_id" not in aa_cols:
        conn.execute("ALTER TABLE article_analysis ADD COLUMN merged_cluster_id INTEGER")
        conn.commit()


def get_connection(db_path: str) -> sqlite3.Connection:
    """Return a configured SQLite connection with WAL mode and foreign keys."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA synchronous=NORMAL")  # safe with WAL, 2-3x faster writes
    conn.execute("PRAGMA cache_size=-64000")  # 64MB cache
    conn.execute("PRAGMA temp_store=MEMORY")  # temp tables in RAM
    return conn


@contextmanager
def connection(db_path: str):
    """Context manager for database connections — auto-closes on exit."""
    conn = get_connection(db_path)
    try:
        yield conn
    finally:
        conn.close()


def parse_datetime(s: str) -> datetime:
    """Parse ISO datetime string, handling +0000 offset format."""
    return datetime.fromisoformat(s.replace("+0000", "+00:00"))


def insert_article(conn: sqlite3.Connection, parsed: dict) -> bool:
    """Insert article dict. Returns True if inserted, False if duplicate."""
    try:
        conn.execute(
            """INSERT INTO articles
               (source_id, headline, summary, source, url, published_at,
                keywords, category, news_desk, word_count)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                parsed["source_id"],
                parsed["headline"],
                parsed["summary"],
                parsed["source"],
                parsed["url"],
                parsed["published_at"],
                parsed["keywords"],
                parsed["category"],
                parsed["news_desk"],
                parsed["word_count"],
            ),
        )
        return True
    except sqlite3.IntegrityError:
        return False
