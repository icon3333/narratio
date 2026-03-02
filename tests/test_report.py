from narratio.db import init_db, get_connection
from narratio.report import generate_report


def test_generate_report_returns_string(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)

    conn.execute("INSERT INTO narratives (id, label, first_seen, last_seen, status) VALUES (1, 'Fed Rate Cuts', '2025-12-01', '2025-12-15', 'active')")
    conn.execute(
        """INSERT INTO narrative_weeks (narrative_id, week_start, article_count, share_of_attention, z_score, sentiment_mean, summary)
           VALUES (1, '2025-12-01', 25, 15.5, 1.2, 0.3, 'Markets expect rate cuts.')"""
    )
    conn.execute(
        """INSERT INTO weekly_totals (week_start, total_articles, total_clustered, total_noise)
           VALUES ('2025-12-01', 161, 130, 31)"""
    )

    for i in range(5):
        conn.execute(
            """INSERT INTO articles (source_id, headline, summary, source, url, published_at, category)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (f"nyt-{i}", f"Fed rate headline {i}", "summary", "test", "http://test.com", "2025-12-01T00:00:00+0000", "general"),
        )
        conn.execute(
            "INSERT INTO article_analysis (article_id, narrative_id) VALUES (?, 1)",
            (i + 1,),
        )
    conn.commit()
    conn.close()

    output = generate_report(db_path)
    assert "Fed Rate Cuts" in output
    assert "15.5" in output or "15.5%" in output
