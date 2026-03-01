"""Finnhub news ingestion."""

import time
from narratio.db import get_connection


def parse_article(raw: dict) -> dict:
    return {
        "finnhub_id": raw["id"],
        "headline": raw.get("headline", ""),
        "summary": raw.get("summary", ""),
        "source": raw.get("source", ""),
        "url": raw.get("url", ""),
        "published_at": raw.get("datetime", 0),
        "related_tickers": raw.get("related", ""),
        "category": raw.get("category", ""),
    }


def ingest_articles(
    client,
    db_path: str,
    category: str = "general",
    max_pages: int = 100,
    delay: float = 1.0,
) -> int:
    conn = get_connection(db_path)
    total_inserted = 0
    min_id = 0

    for page in range(max_pages):
        articles = client.general_news(category, min_id=min_id)
        if not articles:
            break

        for raw in articles:
            parsed = parse_article(raw)
            try:
                conn.execute(
                    """INSERT INTO articles
                       (finnhub_id, headline, summary, source, url,
                        published_at, related_tickers, category)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        parsed["finnhub_id"],
                        parsed["headline"],
                        parsed["summary"],
                        parsed["source"],
                        parsed["url"],
                        parsed["published_at"],
                        parsed["related_tickers"],
                        parsed["category"],
                    ),
                )
                total_inserted += 1
            except Exception:
                pass  # Skip duplicates (UNIQUE constraint on finnhub_id)

        conn.commit()

        batch_ids = [a["id"] for a in articles]
        if not batch_ids:
            break
        min_id = min(batch_ids)

        if len(articles) < 100:
            break

        if delay > 0 and page < max_pages - 1:
            time.sleep(delay)

    conn.close()
    return total_inserted
