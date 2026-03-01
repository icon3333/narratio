from unittest.mock import patch
from narratio.db import init_db, get_connection
from narratio.sentiment import analyze_sentiment, _parse_sentiment_response


def test_parse_sentiment_response():
    raw = '{"score": 0.6, "label": "bullish"}'
    score, label = _parse_sentiment_response(raw)
    assert score == 0.6
    assert label == "bullish"


def test_parse_sentiment_response_handles_plain_text():
    raw = "bullish 0.7"
    score, label = _parse_sentiment_response(raw)
    assert label in ("bullish", "bearish", "neutral")
    assert -1.0 <= score <= 1.0


def test_analyze_sentiment_updates_db(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)

    for i in range(3):
        conn.execute(
            """INSERT INTO articles (finnhub_id, headline, summary, source, url, published_at, category)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (i, f"Headline {i}", f"Summary {i}", "test", "http://test.com", 1700000000, "general"),
        )
        conn.execute(
            "INSERT INTO article_analysis (article_id) VALUES (?)",
            (i + 1,),
        )
    conn.commit()
    conn.close()

    fake_response = {
        "choices": [{"message": {"content": '{"score": 0.5, "label": "bullish"}'}}]
    }

    with patch("narratio.sentiment._call_openrouter_chat") as mock_call:
        mock_call.return_value = fake_response
        count = analyze_sentiment(db_path, "fake-key", batch_size=10)

    assert count == 3

    conn = get_connection(db_path)
    rows = conn.execute("SELECT sentiment_score, sentiment_label FROM article_analysis").fetchall()
    conn.close()

    for r in rows:
        assert r["sentiment_score"] == 0.5
        assert r["sentiment_label"] == "bullish"
