import sqlite3
from narratio.db import init_db, get_connection


def test_init_db_creates_tables(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)

    conn = sqlite3.connect(db_path)
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    )
    tables = [row[0] for row in cursor.fetchall()]
    conn.close()

    assert "articles" in tables
    assert "article_analysis" in tables
    assert "narratives" in tables
    assert "narrative_weeks" in tables
    assert "weekly_totals" in tables


def test_init_db_is_idempotent(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    init_db(db_path)  # Should not raise


def test_get_connection(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)
    assert isinstance(conn, sqlite3.Connection)
    conn.close()
