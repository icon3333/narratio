"""Tests for weekly summarization and analytics computation."""

from unittest.mock import patch, AsyncMock
from narratio.db import init_db, get_connection
from narratio.summarize import compute_weekly_analytics, generate_weekly_summaries, summarize_narratives


def _seed_test_db(db_path):
    """Create a test DB with articles assigned to a narrative."""
    init_db(db_path)
    conn = get_connection(db_path)

    conn.execute(
        "INSERT INTO narratives (id, label, first_seen, last_seen, status) VALUES (1, 'Fed Rate Cuts', '2025-12-01', '2025-12-15', 'active')"
    )

    for i in range(10):
        week_iso = "2024-12-01T00:00:00+0000" if i < 5 else "2024-12-08T00:00:00+0000"
        conn.execute(
            """INSERT INTO articles (source_id, headline, summary, source, url, published_at, category)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (f"nyt-{i}", f"Fed rate headline {i}", f"Summary about rates {i}", "test", "http://test.com", week_iso, "general"),
        )
        conn.execute(
            "INSERT INTO article_analysis (article_id, narrative_id, sentiment_score) VALUES (?, 1, 0.3)",
            (i + 1,),
        )

    conn.commit()
    conn.close()


def test_compute_weekly_analytics_writes_all_rows(tmp_path):
    """Analytics should write narrative_weeks rows for ALL narratives, no LLM needed."""
    db_path = str(tmp_path / "test.db")
    _seed_test_db(db_path)

    count = compute_weekly_analytics(db_path)

    assert count >= 2  # At least 2 weeks of data

    conn = get_connection(db_path)
    weeks = conn.execute("SELECT * FROM narrative_weeks WHERE narrative_id = 1").fetchall()
    totals = conn.execute("SELECT * FROM weekly_totals").fetchall()
    conn.close()

    assert len(weeks) >= 2
    assert len(totals) >= 1
    # Summary should be NULL since no LLM was called
    assert all(w["summary"] is None for w in weeks)
    # But analytics should be populated
    assert all(w["share_of_attention"] is not None for w in weeks)
    assert all(w["article_count"] > 0 for w in weeks)


def test_compute_weekly_analytics_uses_clustered_denominator(tmp_path):
    """Share of attention should use clustered article count, not total."""
    db_path = str(tmp_path / "test.db")
    _seed_test_db(db_path)

    # Add some unclustered articles (no narrative_id)
    conn = get_connection(db_path)
    for i in range(10, 20):
        conn.execute(
            """INSERT INTO articles (source_id, headline, summary, source, url, published_at, category)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (f"nyt-noise-{i}", f"Noise headline {i}", f"Noise {i}", "test", "http://test.com", "2024-12-01T00:00:00+0000", "general"),
        )
        conn.execute(
            "INSERT INTO article_analysis (article_id) VALUES (?)",
            (i + 1,),
        )
    conn.commit()
    conn.close()

    compute_weekly_analytics(db_path)

    conn = get_connection(db_path)
    week1 = conn.execute(
        "SELECT share_of_attention FROM narrative_weeks WHERE narrative_id = 1 AND week_start = '2024-11-25'"
    ).fetchone()
    conn.close()

    # 5 articles out of 5 clustered = 100%, not 5/15 = 33%
    assert week1 is not None
    assert week1["share_of_attention"] == 100.0


def test_compute_weekly_analytics_preserves_existing_summaries(tmp_path):
    """Re-running analytics should not erase existing summaries."""
    db_path = str(tmp_path / "test.db")
    _seed_test_db(db_path)

    # First run: write rows
    compute_weekly_analytics(db_path)

    # Manually set a summary
    conn = get_connection(db_path)
    conn.execute(
        "UPDATE narrative_weeks SET summary = 'existing summary' WHERE narrative_id = 1 AND week_start = (SELECT MIN(week_start) FROM narrative_weeks)"
    )
    conn.commit()
    conn.close()

    # Re-run analytics
    compute_weekly_analytics(db_path)

    conn = get_connection(db_path)
    row = conn.execute(
        "SELECT summary FROM narrative_weeks WHERE narrative_id = 1 AND week_start = (SELECT MIN(week_start) FROM narrative_weeks WHERE narrative_id = 1)"
    ).fetchone()
    conn.close()

    assert row["summary"] == "existing summary"


def test_generate_weekly_summaries_fills_null_summaries(tmp_path):
    """LLM summaries should fill NULL summary rows."""
    db_path = str(tmp_path / "test.db")
    _seed_test_db(db_path)

    # First compute analytics (creates rows with NULL summaries)
    compute_weekly_analytics(db_path)

    fake_response = {
        "choices": [{"message": {"content": "Markets increasingly expect rate cuts."}}]
    }

    mock_call = AsyncMock(return_value=fake_response)
    with patch("narratio.summarize._call_openrouter_chat_async", mock_call):
        count = generate_weekly_summaries(db_path, "fake-key")

    assert count >= 1

    conn = get_connection(db_path)
    weeks = conn.execute(
        "SELECT summary FROM narrative_weeks WHERE narrative_id = 1 AND summary IS NOT NULL"
    ).fetchall()
    conn.close()

    assert len(weeks) >= 1


def test_legacy_summarize_narratives(tmp_path):
    """Legacy entrypoint should call both analytics + summaries."""
    db_path = str(tmp_path / "test.db")
    _seed_test_db(db_path)

    fake_response = {
        "choices": [{"message": {"content": "Markets increasingly expect rate cuts."}}]
    }

    mock_call = AsyncMock(return_value=fake_response)
    with patch("narratio.summarize._call_openrouter_chat_async", mock_call):
        count = summarize_narratives(db_path, "fake-key")

    assert count >= 1

    conn = get_connection(db_path)
    weeks = conn.execute("SELECT * FROM narrative_weeks WHERE narrative_id = 1").fetchall()
    totals = conn.execute("SELECT * FROM weekly_totals").fetchall()
    conn.close()

    assert len(weeks) >= 1
    assert len(totals) >= 1
