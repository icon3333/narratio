import pandas as pd
from narratio.db import init_db, get_connection
from narratio.data import (
    get_narratives_df,
    get_timeline_df,
    get_narrative_detail,
    get_narrative_headlines,
)


def _seed_db(db_path):
    init_db(db_path)
    conn = get_connection(db_path)

    conn.execute("INSERT INTO narratives (id, label, first_seen, last_seen, status) VALUES (1, 'Fed Rate Cuts', '2025-12-01', '2025-12-22', 'active')")
    conn.execute("INSERT INTO narratives (id, label, first_seen, last_seen, status) VALUES (2, 'AI Hype Cycle', '2025-12-01', '2025-12-22', 'active')")

    for i, ws in enumerate(["2025-12-01", "2025-12-08", "2025-12-15"]):
        conn.execute(
            "INSERT INTO narrative_weeks (narrative_id, week_start, article_count, share_of_attention, z_score, sentiment_mean, summary, top_headline_ids) VALUES (1, ?, ?, ?, ?, ?, ?, ?)",
            (ws, 20 + i * 5, 15.0 + i * 5, 0.5 + i * 0.3, 0.3, f"Fed summary week {i+1}", "[1,2,3]"),
        )
        conn.execute(
            "INSERT INTO narrative_weeks (narrative_id, week_start, article_count, share_of_attention, z_score, sentiment_mean, summary, top_headline_ids) VALUES (2, ?, ?, ?, ?, ?, ?, ?)",
            (ws, 30 - i * 5, 25.0 - i * 5, -0.2 + i * 0.1, -0.1, f"AI summary week {i+1}", "[4,5,6]"),
        )

    for ws in ["2025-12-01", "2025-12-08", "2025-12-15"]:
        conn.execute("INSERT INTO weekly_totals (week_start, total_articles, total_clustered, total_noise) VALUES (?, 200, 150, 50)", (ws,))

    for i in range(6):
        nar_id = 1 if i < 3 else 2
        conn.execute(
            "INSERT INTO articles (nyt_id, headline, summary, source, url, published_at, category) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (f"nyt-{i}", f"Headline {i} for narrative {nar_id}", f"Summary {i}", "reuters", "http://example.com", f"2025-12-{1 + i:02d}T00:00:00Z", "general"),
        )
        conn.execute(
            "INSERT INTO article_analysis (article_id, narrative_id, sentiment_score, sentiment_label) VALUES (?, ?, ?, ?)",
            (i + 1, nar_id, 0.3 if nar_id == 1 else -0.1, "bullish" if nar_id == 1 else "neutral"),
        )

    conn.commit()
    conn.close()


def test_get_narratives_df(tmp_path):
    db_path = str(tmp_path / "test.db")
    _seed_db(db_path)
    df = get_narratives_df(db_path)
    assert isinstance(df, pd.DataFrame)
    assert len(df) == 2
    assert "label" in df.columns
    assert "article_count" in df.columns


def test_get_timeline_df(tmp_path):
    db_path = str(tmp_path / "test.db")
    _seed_db(db_path)
    df = get_timeline_df(db_path)
    assert isinstance(df, pd.DataFrame)
    assert len(df) == 6
    assert "week_start" in df.columns
    assert "share_of_attention" in df.columns
    assert "label" in df.columns


def test_get_narrative_detail(tmp_path):
    db_path = str(tmp_path / "test.db")
    _seed_db(db_path)
    detail = get_narrative_detail(db_path, 1)
    assert detail["label"] == "Fed Rate Cuts"
    assert len(detail["weeks"]) == 3


def test_get_narrative_headlines(tmp_path):
    db_path = str(tmp_path / "test.db")
    _seed_db(db_path)
    headlines = get_narrative_headlines(db_path, 1, limit=5)
    assert len(headlines) >= 1
    assert "headline" in headlines[0]
