"""Guardian Open Platform API ingestion."""

import json
import logging
import time
import httpx
from narratio.db import get_connection, insert_article

logger = logging.getLogger(__name__)

GUARDIAN_URL = "https://content.guardianapis.com/search"

RELEVANT_SECTIONS = {
    "business", "world", "us-news", "technology", "money",
}


def _fetch_page(api_key: str, year: int, month: int, page: int = 1, max_retries: int = 3) -> dict:
    from_date = f"{year}-{month:02d}-01"
    if month == 12:
        to_date = f"{year + 1}-01-01"
    else:
        to_date = f"{year}-{month + 1:02d}-01"

    for attempt in range(max_retries):
        try:
            resp = httpx.get(
                GUARDIAN_URL,
                params={
                    "api-key": api_key,
                    "from-date": from_date,
                    "to-date": to_date,
                    "section": "|".join(RELEVANT_SECTIONS),
                    "show-fields": "headline,trailText,wordcount,shortUrl",
                    "page-size": 200,
                    "page": page,
                    "order-by": "newest",
                },
                timeout=60,
            )
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code < 500:
                raise  # don't retry client errors
            if attempt == max_retries - 1:
                raise
            wait = 2 ** attempt * 5
            logger.warning("Guardian fetch failed (attempt %d/%d): %s — retrying in %ds", attempt + 1, max_retries, e, wait)
            time.sleep(wait)
        except httpx.TransportError as e:
            if attempt == max_retries - 1:
                raise
            wait = 2 ** attempt * 5
            logger.warning("Guardian fetch failed (attempt %d/%d): %s — retrying in %ds", attempt + 1, max_retries, e, wait)
            time.sleep(wait)
    return {}  # unreachable, but satisfies type checker


def parse_guardian_article(raw: dict) -> dict | None:
    fields = raw.get("fields", {})
    headline = fields.get("headline") or raw.get("webTitle", "")
    if not headline:
        return None

    word_count = int(fields.get("wordcount", 0) or 0)
    if word_count == 0:
        return None

    return {
        "source_id": f"guardian:{raw['id']}",
        "headline": headline,
        "summary": fields.get("trailText", "") or "",
        "source": "The Guardian",
        "url": raw.get("webUrl", ""),
        "published_at": raw.get("webPublicationDate", ""),
        "keywords": json.dumps([]),
        "category": raw.get("sectionName", ""),
        "news_desk": raw.get("sectionId", ""),
        "word_count": word_count,
    }


def ingest_month(
    db_path: str,
    api_key: str,
    year: int,
    month: int,
    delay: float = 1.0,
) -> int:
    """Fetch all Guardian articles for a given month. Paginates automatically."""
    logger.info("Fetching Guardian articles for %d-%02d", year, month)
    page = 1
    total_pages = 1
    inserted = 0
    skipped = 0
    conn = get_connection(db_path)

    try:
        while page <= total_pages:
            data = _fetch_page(api_key, year, month, page)
            response = data.get("response", {})
            total_pages = min(response.get("pages", 1), 50)  # cap at 50 pages
            results = response.get("results", [])

            for raw in results:
                parsed = parse_guardian_article(raw)
                if parsed is None:
                    continue
                if insert_article(conn, parsed):
                    inserted += 1
                else:
                    skipped += 1

            page += 1
            if page <= total_pages and delay > 0:
                time.sleep(delay)

        conn.commit()
    finally:
        conn.close()
    logger.info("Guardian %d-%02d: inserted=%d, skipped_dupes=%d, pages=%d", year, month, inserted, skipped, page - 1)
    return inserted


def ingest_range(
    db_path: str,
    api_key: str,
    start_year: int,
    start_month: int,
    end_year: int,
    end_month: int,
    delay: float = 1.0,
) -> int:
    total = 0
    year, month = start_year, start_month

    while (year, month) <= (end_year, end_month):
        count = ingest_month(db_path, api_key, year, month, delay=delay)
        total += count

        month += 1
        if month > 12:
            month = 1
            year += 1

    return total
