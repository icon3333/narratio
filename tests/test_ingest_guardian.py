from narratio.db import init_db, get_connection
from narratio.ingest_guardian import parse_guardian_article, ingest_month
from unittest.mock import patch


def _make_guardian_article(id="business/2026/mar/01/test-article", headline="Test Headline"):
    return {
        "id": id,
        "webTitle": "Test Web Title",
        "webUrl": "https://theguardian.com/test",
        "webPublicationDate": "2026-03-01T10:30:00Z",
        "sectionName": "Business",
        "sectionId": "business",
        "fields": {
            "headline": headline,
            "trailText": "Test trail text summary",
            "wordcount": "800",
            "shortUrl": "https://gu.com/test",
        },
    }


def test_parse_guardian_article():
    raw = _make_guardian_article()
    parsed = parse_guardian_article(raw)
    assert parsed["source_id"] == "guardian:business/2026/mar/01/test-article"
    assert parsed["headline"] == "Test Headline"
    assert parsed["summary"] == "Test trail text summary"
    assert parsed["source"] == "The Guardian"
    assert parsed["word_count"] == 800


def test_parse_guardian_article_skips_zero_wordcount():
    raw = _make_guardian_article()
    raw["fields"]["wordcount"] = "0"
    parsed = parse_guardian_article(raw)
    assert parsed is None


def test_ingest_month_inserts(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)

    articles = [
        _make_guardian_article(id="business/1", headline="Article one"),
        _make_guardian_article(id="business/2", headline="Article two"),
    ]
    mock_response = {
        "response": {
            "pages": 1,
            "results": articles,
        }
    }

    with patch("narratio.ingest_guardian._fetch_page") as mock_fetch:
        mock_fetch.return_value = mock_response
        count = ingest_month(db_path, "fake-key", 2026, 3)

    assert count == 2

    conn = get_connection(db_path)
    rows = conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
    conn.close()
    assert rows == 2


def test_ingest_month_skips_duplicates(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)

    articles = [_make_guardian_article(id="business/1")]
    mock_response = {"response": {"pages": 1, "results": articles}}

    with patch("narratio.ingest_guardian._fetch_page") as mock_fetch:
        mock_fetch.return_value = mock_response
        ingest_month(db_path, "fake-key", 2026, 3)
        ingest_month(db_path, "fake-key", 2026, 3)

    conn = get_connection(db_path)
    rows = conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
    conn.close()
    assert rows == 1
