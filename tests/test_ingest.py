import json
from narratio.db import init_db, get_connection
from narratio.ingest import parse_nyt_article, ingest_month, RELEVANT_SECTIONS
from unittest.mock import patch


def _make_nyt_article(id="nyt://article/test-1", headline="Test Headline", section="Business"):
    return {
        "_id": id,
        "headline": {"main": headline},
        "abstract": "Test abstract",
        "lead_paragraph": "Test lead paragraph",
        "snippet": "Test snippet",
        "pub_date": "2025-06-15T10:30:00+0000",
        "web_url": "https://nytimes.com/test",
        "source": "The New York Times",
        "section_name": section,
        "news_desk": "Business",
        "type_of_material": "News",
        "document_type": "article",
        "word_count": 800,
        "keywords": [
            {"name": "subject", "value": "Interest Rates"},
            {"name": "organizations", "value": "Federal Reserve"},
        ],
    }


def test_parse_nyt_article():
    raw = _make_nyt_article()
    parsed = parse_nyt_article(raw)
    assert parsed["nyt_id"] == "nyt://article/test-1"
    assert parsed["headline"] == "Test Headline"
    assert parsed["summary"] == "Test abstract"
    assert parsed["published_at"] == "2025-06-15T10:30:00+0000"
    assert parsed["category"] == "Business"
    assert "Interest Rates" in parsed["keywords"]


def test_parse_nyt_article_uses_lead_paragraph_fallback():
    raw = _make_nyt_article()
    raw["abstract"] = ""
    parsed = parse_nyt_article(raw)
    assert parsed["summary"] == "Test lead paragraph"


def test_ingest_month_inserts_and_filters(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)

    docs = [
        _make_nyt_article(id="nyt://1", headline="Business article", section="Business"),
        _make_nyt_article(id="nyt://2", headline="Sports article", section="Sports"),  # filtered out
        _make_nyt_article(id="nyt://3", headline="World article", section="World"),
    ]
    # Make the Sports one a News article too so only section filtering applies
    for d in docs:
        d["type_of_material"] = "News"
        d["document_type"] = "article"

    mock_response = {"response": {"docs": docs}}

    with patch("narratio.ingest._fetch_archive") as mock_fetch:
        mock_fetch.return_value = mock_response
        count = ingest_month(db_path, "fake-key", 2025, 6)

    assert count == 2  # Sports filtered out

    conn = get_connection(db_path)
    rows = conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
    conn.close()
    assert rows == 2


def test_ingest_month_skips_duplicates(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)

    docs = [_make_nyt_article(id="nyt://1")]
    mock_response = {"response": {"docs": docs}}

    with patch("narratio.ingest._fetch_archive") as mock_fetch:
        mock_fetch.return_value = mock_response
        ingest_month(db_path, "fake-key", 2025, 6)
        ingest_month(db_path, "fake-key", 2025, 6)

    conn = get_connection(db_path)
    rows = conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
    conn.close()
    assert rows == 1
