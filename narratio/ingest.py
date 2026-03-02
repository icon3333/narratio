"""NYT Archive API ingestion."""

import json
import logging
import sqlite3
import time
import httpx
from narratio.db import get_connection

logger = logging.getLogger(__name__)

NYT_ARCHIVE_URL = "https://api.nytimes.com/svc/archive/v1/{year}/{month}.json"

RELEVANT_SECTIONS = {
    "Business", "Business Day", "World", "U.S.", "Technology",
    "Science", "DealBook", "Economy", "Your Money",
}


def _fetch_archive(api_key: str, year: int, month: int) -> dict:
    url = NYT_ARCHIVE_URL.format(year=year, month=month)
    resp = httpx.get(url, params={"api-key": api_key}, timeout=120)
    resp.raise_for_status()
    return resp.json()


def parse_nyt_article(raw: dict) -> dict:
    headline_obj = raw.get("headline", {})
    headline = headline_obj.get("main", "") if isinstance(headline_obj, dict) else ""
    summary = raw.get("abstract", "") or raw.get("lead_paragraph", "") or raw.get("snippet", "")

    keywords_list = raw.get("keywords", [])
    keywords_str = json.dumps([kw.get("value", "") for kw in keywords_list]) if keywords_list else "[]"

    return {
        "source_id": raw.get("_id", ""),
        "headline": headline,
        "summary": summary,
        "source": raw.get("source", "The New York Times"),
        "url": raw.get("web_url", ""),
        "published_at": raw.get("pub_date", ""),
        "keywords": keywords_str,
        "category": raw.get("section_name", ""),
        "news_desk": raw.get("news_desk", ""),
        "word_count": raw.get("word_count", 0) or 0,
    }


def _should_include(raw: dict) -> bool:
    if raw.get("document_type") != "article":
        return False
    if raw.get("type_of_material") != "News":
        return False
    section = raw.get("section_name", "")
    if section not in RELEVANT_SECTIONS:
        return False
    if not raw.get("headline", {}).get("main"):
        return False
    if (raw.get("word_count") or 0) == 0:
        return False
    return True


def ingest_month(
    db_path: str,
    api_key: str,
    year: int,
    month: int,
) -> int:
    logger.info("Fetching NYT archive for %d-%02d", year, month)
    data = _fetch_archive(api_key, year, month)
    docs = data.get("response", {}).get("docs", [])
    logger.info("Received %d documents from NYT archive", len(docs))

    conn = get_connection(db_path)
    inserted = 0
    skipped = 0

    for raw in docs:
        if not _should_include(raw):
            continue

        parsed = parse_nyt_article(raw)
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
            inserted += 1
        except sqlite3.IntegrityError:
            skipped += 1

    conn.commit()
    conn.close()
    logger.info("NYT %d-%02d: inserted=%d, skipped_dupes=%d", year, month, inserted, skipped)
    return inserted


def ingest_range(
    db_path: str,
    api_key: str,
    start_year: int,
    start_month: int,
    end_year: int,
    end_month: int,
    delay: float = 12.0,
) -> int:
    total = 0
    year, month = start_year, start_month

    while (year, month) <= (end_year, end_month):
        count = ingest_month(db_path, api_key, year, month)
        total += count

        month += 1
        if month > 12:
            month = 1
            year += 1

        if (year, month) <= (end_year, end_month) and delay > 0:
            time.sleep(delay)

    return total
