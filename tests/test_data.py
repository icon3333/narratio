import pandas as pd
from narratio.db import init_db, get_connection
from narratio.data import (
    get_narratives_df,
    get_timeline_df,
    get_timeline_with_other,
    get_narrative_detail,
    get_narrative_headlines,
    compute_significance_scores,
    get_top_narrative_ids,
    get_top_narrative_ids_for_window,
)


def _seed_db(db_path):
    init_db(db_path)
    conn = get_connection(db_path)

    conn.execute("INSERT INTO narratives (id, label, first_seen, last_seen, status) VALUES (1, 'Fed Rate Cuts', '2025-12-01', '2025-12-22', 'active')")
    conn.execute("INSERT INTO narratives (id, label, first_seen, last_seen, status) VALUES (2, 'AI Hype Cycle', '2025-12-01', '2025-12-22', 'active')")
    conn.execute("INSERT INTO narratives (id, label, first_seen, last_seen, status) VALUES (3, 'Small Narrative', '2025-12-01', '2025-12-08', 'active')")

    for i, ws in enumerate(["2025-12-01", "2025-12-08", "2025-12-15"]):
        conn.execute(
            "INSERT INTO narrative_weeks (narrative_id, week_start, article_count, share_of_attention, z_score, sentiment_mean, summary, top_headline_ids) VALUES (1, ?, ?, ?, ?, ?, ?, ?)",
            (ws, 20 + i * 5, 15.0 + i * 5, 0.5 + i * 0.3, 0.3, f"Fed summary week {i+1}", "[1,2,3]"),
        )
        conn.execute(
            "INSERT INTO narrative_weeks (narrative_id, week_start, article_count, share_of_attention, z_score, sentiment_mean, summary, top_headline_ids) VALUES (2, ?, ?, ?, ?, ?, ?, ?)",
            (ws, 30 - i * 5, 25.0 - i * 5, -0.2 + i * 0.1, -0.1, f"AI summary week {i+1}", "[4,5,6]"),
        )

    # Small narrative: only 1 week
    conn.execute(
        "INSERT INTO narrative_weeks (narrative_id, week_start, article_count, share_of_attention, z_score, sentiment_mean, summary, top_headline_ids) VALUES (3, '2025-12-01', 5, 3.0, 0.1, 0.0, 'Small summary', '[7]')"
    )

    for ws in ["2025-12-01", "2025-12-08", "2025-12-15"]:
        conn.execute("INSERT INTO weekly_totals (week_start, total_articles, total_clustered, total_noise) VALUES (?, 200, 150, 50)", (ws,))

    for i in range(6):
        nar_id = 1 if i < 3 else 2
        conn.execute(
            "INSERT INTO articles (source_id, headline, summary, source, url, published_at, category) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (f"nyt-{i}", f"Headline {i} for narrative {nar_id}", f"Summary {i}", "reuters", "http://example.com", f"2025-12-{1 + i:02d}T00:00:00Z", "general"),
        )
        conn.execute(
            "INSERT INTO article_analysis (article_id, narrative_id, sentiment_score, sentiment_label) VALUES (?, ?, ?, ?)",
            (i + 1, nar_id, 0.3 if nar_id == 1 else -0.1, "bullish" if nar_id == 1 else "neutral"),
        )

    # Add articles for narrative 3 so it passes the article_count > 0 filter
    conn.execute(
        "INSERT INTO articles (source_id, headline, summary, source, url, published_at, category) VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("nyt-6", "Headline for narrative 3", "Summary 6", "reuters", "http://example.com", "2025-12-01T00:00:00Z", "general"),
    )
    conn.execute(
        "INSERT INTO article_analysis (article_id, narrative_id, sentiment_score, sentiment_label) VALUES (?, ?, ?, ?)",
        (7, 3, 0.0, "neutral"),
    )

    conn.commit()
    conn.close()


def test_get_narratives_df(tmp_path):
    db_path = str(tmp_path / "test.db")
    _seed_db(db_path)
    df = get_narratives_df(db_path)
    assert isinstance(df, pd.DataFrame)
    assert len(df) == 3
    assert "label" in df.columns
    assert "article_count" in df.columns
    assert "significance_score" in df.columns


def test_get_timeline_df(tmp_path):
    db_path = str(tmp_path / "test.db")
    _seed_db(db_path)
    df = get_timeline_df(db_path)
    assert isinstance(df, pd.DataFrame)
    assert len(df) == 7  # 3 + 3 + 1
    assert "week_start" in df.columns
    assert "share_of_attention" in df.columns
    assert "label" in df.columns


def test_get_narrative_detail(tmp_path):
    db_path = str(tmp_path / "test.db")
    _seed_db(db_path)
    detail = get_narrative_detail(db_path, 1)
    assert detail["label"] == "Fed Rate Cuts"
    assert len(detail["weeks"]) == 3
    assert "significance_score" in detail


def test_get_narrative_headlines(tmp_path):
    db_path = str(tmp_path / "test.db")
    _seed_db(db_path)
    headlines = get_narrative_headlines(db_path, 1, limit=5)
    assert len(headlines) >= 1
    assert "headline" in headlines[0]


def test_compute_significance_scores(tmp_path):
    db_path = str(tmp_path / "test.db")
    _seed_db(db_path)
    count = compute_significance_scores(db_path)
    assert count == 3

    conn = get_connection(db_path)
    rows = conn.execute("SELECT id, significance_score FROM narratives ORDER BY significance_score DESC").fetchall()
    conn.close()

    # All should have scores
    assert all(r["significance_score"] is not None for r in rows)
    # Higher-activity narratives should score higher
    scores = {r["id"]: r["significance_score"] for r in rows}
    assert scores[1] > scores[3]  # Fed > Small


def test_get_top_narrative_ids(tmp_path):
    db_path = str(tmp_path / "test.db")
    _seed_db(db_path)
    compute_significance_scores(db_path)

    top = get_top_narrative_ids(db_path, top_n=2)
    assert len(top) == 2
    # Small narrative should not be in top 2
    assert 3 not in top


def test_get_timeline_with_other(tmp_path):
    db_path = str(tmp_path / "test.db")
    _seed_db(db_path)
    compute_significance_scores(db_path)

    df = get_timeline_with_other(db_path, top_n=2)
    assert isinstance(df, pd.DataFrame)
    assert not df.empty

    labels = df["label"].unique().tolist()
    assert "Other" in labels
    # Should have top 2 narratives + Other
    assert len([l for l in labels if l != "Other"]) == 2

    # "Other" rows should have aggregated data
    other_rows = df[df["label"] == "Other"]
    assert all(other_rows["narrative_id"] == -1)
    assert all(other_rows["article_count"] > 0)


def _seed_db_temporal(db_path):
    """Seed DB with narratives that are active in different time periods.

    - Narrative 1 "Early Narrative": active only in Oct 2025
    - Narrative 2 "Late Narrative": active only in Dec 2025
    - Narrative 3 "Persistent Narrative": active Oct-Dec 2025
    """
    init_db(db_path)
    conn = get_connection(db_path)

    conn.execute("INSERT INTO narratives (id, label, first_seen, last_seen, status) VALUES (1, 'Early Narrative', '2025-10-06', '2025-10-27', 'active')")
    conn.execute("INSERT INTO narratives (id, label, first_seen, last_seen, status) VALUES (2, 'Late Narrative', '2025-12-01', '2025-12-22', 'active')")
    conn.execute("INSERT INTO narratives (id, label, first_seen, last_seen, status) VALUES (3, 'Persistent Narrative', '2025-10-06', '2025-12-22', 'active')")

    # Early Narrative: big in October, nothing after
    for ws in ["2025-10-06", "2025-10-13", "2025-10-20", "2025-10-27"]:
        conn.execute(
            "INSERT INTO narrative_weeks (narrative_id, week_start, article_count, share_of_attention, z_score, sentiment_mean, summary, top_headline_ids) VALUES (1, ?, 30, 25.0, 1.5, 0.2, 'Early summary', '[1]')",
            (ws,),
        )

    # Late Narrative: big in December, nothing before
    for ws in ["2025-12-01", "2025-12-08", "2025-12-15", "2025-12-22"]:
        conn.execute(
            "INSERT INTO narrative_weeks (narrative_id, week_start, article_count, share_of_attention, z_score, sentiment_mean, summary, top_headline_ids) VALUES (2, ?, 25, 20.0, 1.2, -0.1, 'Late summary', '[2]')",
            (ws,),
        )

    # Persistent Narrative: moderate throughout
    for ws in ["2025-10-06", "2025-10-13", "2025-10-20", "2025-10-27",
               "2025-11-03", "2025-11-10", "2025-11-17", "2025-11-24",
               "2025-12-01", "2025-12-08", "2025-12-15", "2025-12-22"]:
        conn.execute(
            "INSERT INTO narrative_weeks (narrative_id, week_start, article_count, share_of_attention, z_score, sentiment_mean, summary, top_headline_ids) VALUES (3, ?, 10, 8.0, 0.3, 0.0, 'Persistent summary', '[3]')",
            (ws,),
        )

    # Weekly totals for all weeks
    for ws in ["2025-10-06", "2025-10-13", "2025-10-20", "2025-10-27",
               "2025-11-03", "2025-11-10", "2025-11-17", "2025-11-24",
               "2025-12-01", "2025-12-08", "2025-12-15", "2025-12-22"]:
        conn.execute("INSERT INTO weekly_totals (week_start, total_articles, total_clustered, total_noise) VALUES (?, 200, 150, 50)", (ws,))

    # Minimal articles so narratives pass the article_count > 0 filter
    for i, nid in enumerate([1, 2, 3], start=1):
        conn.execute(
            "INSERT INTO articles (source_id, headline, summary, source, url, published_at, category) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (f"nyt-{i}", f"Headline {i}", f"Summary {i}", "reuters", "http://example.com", "2025-11-01T00:00:00Z", "general"),
        )
        conn.execute(
            "INSERT INTO article_analysis (article_id, narrative_id, sentiment_score, sentiment_label) VALUES (?, ?, 0.0, 'neutral')",
            (i, nid),
        )

    conn.commit()
    conn.close()


def test_corrupt_z_scores_clamped(tmp_path):
    """Corrupt z_scores should be clamped so they don't produce extreme significance scores."""
    db_path = str(tmp_path / "test.db")
    _seed_db(db_path)

    # Inject corrupt z_score values
    conn = get_connection(db_path)
    conn.execute("UPDATE narrative_weeks SET z_score = 8.6e15 WHERE narrative_id = 3")
    conn.commit()
    conn.close()

    count = compute_significance_scores(db_path)
    assert count == 3

    conn = get_connection(db_path)
    rows = conn.execute(
        "SELECT id, significance_score FROM narratives ORDER BY significance_score DESC"
    ).fetchall()
    conn.close()

    # All scores should be <= 1.0 (normalized)
    for r in rows:
        assert r["significance_score"] <= 1.0, (
            f"Narrative {r['id']} has score {r['significance_score']} > 1.0"
        )


def test_top_narrative_ids_excludes_dormant(tmp_path):
    """get_top_narrative_ids should only return active narratives."""
    db_path = str(tmp_path / "test.db")
    _seed_db(db_path)
    compute_significance_scores(db_path)

    # Mark narrative 1 as dormant — it should be excluded from top IDs
    conn = get_connection(db_path)
    conn.execute("UPDATE narratives SET status = 'dormant' WHERE id = 1")
    conn.commit()
    conn.close()

    top = get_top_narrative_ids(db_path, top_n=12)
    assert 1 not in top
    assert len(top) == 2  # only narratives 2 and 3 remain active


def test_window_scoring_excludes_dormant(tmp_path):
    """get_top_narrative_ids_for_window should only return active narratives."""
    db_path = str(tmp_path / "test.db")
    _seed_db_temporal(db_path)

    # Mark narrative 1 as dormant
    conn = get_connection(db_path)
    conn.execute("UPDATE narratives SET status = 'dormant' WHERE id = 1")
    conn.commit()
    conn.close()

    top = get_top_narrative_ids_for_window(
        db_path, top_n=3, start="2025-10-01", end="2025-10-31"
    )
    assert 1 not in top  # dormant, should be excluded


def test_window_scoring_october_only(tmp_path):
    """In Oct window, Early Narrative should rank highest (most activity)."""
    db_path = str(tmp_path / "test.db")
    _seed_db_temporal(db_path)

    top = get_top_narrative_ids_for_window(
        db_path, top_n=3, start="2025-10-01", end="2025-10-31"
    )
    # Early Narrative (id=1) should be #1 in October
    assert top[0] == 1
    # Late Narrative (id=2) should be excluded — zero activity in October
    assert 2 not in top


def test_window_scoring_december_only(tmp_path):
    """In Dec window, Late Narrative should rank highest."""
    db_path = str(tmp_path / "test.db")
    _seed_db_temporal(db_path)

    top = get_top_narrative_ids_for_window(
        db_path, top_n=3, start="2025-12-01", end="2025-12-31"
    )
    # Late Narrative (id=2) should be #1 in December
    assert top[0] == 2
    # Early Narrative (id=1) should be excluded — zero activity in December
    assert 1 not in top


def test_window_scoring_all_time(tmp_path):
    """With no window, falls back to global significance scores."""
    db_path = str(tmp_path / "test.db")
    _seed_db_temporal(db_path)
    compute_significance_scores(db_path)

    top_windowed = get_top_narrative_ids_for_window(db_path, top_n=3)
    top_global = get_top_narrative_ids(db_path, top_n=3)
    assert top_windowed == top_global


def test_timeline_with_other_uses_window_scoring(tmp_path):
    """get_timeline_with_other should surface different narratives for different windows."""
    db_path = str(tmp_path / "test.db")
    _seed_db_temporal(db_path)
    compute_significance_scores(db_path)

    # October view: should include Early Narrative, not Late
    df_oct = get_timeline_with_other(db_path, top_n=2, start="2025-10-01", end="2025-10-31")
    oct_labels = df_oct[df_oct["label"] != "Other"]["label"].unique().tolist()
    assert "Early Narrative" in oct_labels
    assert "Late Narrative" not in oct_labels

    # December view: should include Late Narrative, not Early
    df_dec = get_timeline_with_other(db_path, top_n=2, start="2025-12-01", end="2025-12-31")
    dec_labels = df_dec[df_dec["label"] != "Other"]["label"].unique().tolist()
    assert "Late Narrative" in dec_labels
    assert "Early Narrative" not in dec_labels
