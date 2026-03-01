"""Tests for weekly summarization and analytics computation."""

from unittest.mock import patch
from narratio.db import init_db, get_connection
from narratio.summarize import summarize_narratives


def test_summarize_narratives_creates_weekly_records(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)

    conn.execute(
        "INSERT INTO narratives (id, label, first_seen, last_seen, status) VALUES (1, 'Fed Rate Cuts', '2025-12-01', '2025-12-15', 'active')"
    )

    for i in range(10):
        week_ts = 1733011200 if i < 5 else 1733616000  # Dec 1 and Dec 8 2024
        conn.execute(
            """INSERT INTO articles (finnhub_id, headline, summary, source, url, published_at, category)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (i, f"Fed rate headline {i}", f"Summary about rates {i}", "test", "http://test.com", week_ts, "general"),
        )
        conn.execute(
            "INSERT INTO article_analysis (article_id, narrative_id, sentiment_score) VALUES (?, 1, 0.3)",
            (i + 1,),
        )

    conn.commit()
    conn.close()

    fake_response = {
        "choices": [{"message": {"content": "Markets increasingly expect rate cuts as economic data softens."}}]
    }

    with patch("narratio.summarize._call_openrouter_chat") as mock_call:
        mock_call.return_value = fake_response
        count = summarize_narratives(db_path, "fake-key")

    assert count >= 1

    conn = get_connection(db_path)
    weeks = conn.execute("SELECT * FROM narrative_weeks WHERE narrative_id = 1").fetchall()
    totals = conn.execute("SELECT * FROM weekly_totals").fetchall()
    conn.close()

    assert len(weeks) >= 1
    assert len(totals) >= 1
    assert weeks[0]["summary"] is not None
