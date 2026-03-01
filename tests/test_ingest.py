import sqlite3
from unittest.mock import MagicMock
from narratio.db import init_db, get_connection
from narratio.ingest import parse_article, ingest_articles


def _make_finnhub_article(id=1, headline="Test headline", summary="Test summary"):
    return {
        "id": id,
        "headline": headline,
        "summary": summary,
        "source": "reuters",
        "url": "https://example.com/1",
        "datetime": 1700000000,
        "related": "AAPL,MSFT",
        "category": "general",
    }


def test_parse_article():
    raw = _make_finnhub_article()
    parsed = parse_article(raw)
    assert parsed["finnhub_id"] == 1
    assert parsed["headline"] == "Test headline"
    assert parsed["related_tickers"] == "AAPL,MSFT"


def test_ingest_articles_inserts_rows(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)

    articles = [_make_finnhub_article(id=i, headline=f"Headline {i}") for i in range(5)]

    mock_client = MagicMock()
    mock_client.general_news.return_value = articles

    count = ingest_articles(mock_client, db_path, category="general", max_pages=1)
    assert count == 5

    conn = get_connection(db_path)
    rows = conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
    conn.close()
    assert rows == 5


def test_ingest_articles_skips_duplicates(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)

    articles = [_make_finnhub_article(id=1)]
    mock_client = MagicMock()
    mock_client.general_news.return_value = articles

    ingest_articles(mock_client, db_path, category="general", max_pages=1)
    ingest_articles(mock_client, db_path, category="general", max_pages=1)

    conn = get_connection(db_path)
    rows = conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
    conn.close()
    assert rows == 1
