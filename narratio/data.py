"""Data access layer — returns pandas DataFrames from SQLite for Streamlit."""

import pandas as pd
from narratio.db import get_connection


def get_narratives_df(db_path: str) -> pd.DataFrame:
    conn = get_connection(db_path)
    df = pd.read_sql_query(
        """SELECT n.id, n.label, n.first_seen, n.last_seen, n.status,
                  COUNT(aa.article_id) as article_count
           FROM narratives n
           LEFT JOIN article_analysis aa ON aa.narrative_id = n.id
           GROUP BY n.id
           ORDER BY article_count DESC""",
        conn,
    )
    conn.close()
    return df


def get_timeline_df(db_path: str) -> pd.DataFrame:
    conn = get_connection(db_path)
    df = pd.read_sql_query(
        """SELECT nw.narrative_id, n.label, nw.week_start,
                  nw.article_count, nw.share_of_attention,
                  nw.z_score, nw.sentiment_mean
           FROM narrative_weeks nw
           JOIN narratives n ON n.id = nw.narrative_id
           ORDER BY nw.week_start, nw.share_of_attention DESC""",
        conn,
    )
    conn.close()
    df["week_start"] = pd.to_datetime(df["week_start"])
    return df


def get_narrative_detail(db_path: str, narrative_id: int) -> dict:
    conn = get_connection(db_path)
    narrative = conn.execute("SELECT * FROM narratives WHERE id = ?", (narrative_id,)).fetchone()
    weeks = conn.execute(
        "SELECT * FROM narrative_weeks WHERE narrative_id = ? ORDER BY week_start",
        (narrative_id,),
    ).fetchall()
    conn.close()
    return {
        "id": narrative["id"],
        "label": narrative["label"],
        "first_seen": narrative["first_seen"],
        "last_seen": narrative["last_seen"],
        "status": narrative["status"],
        "weeks": [dict(w) for w in weeks],
    }


def get_narrative_headlines(db_path: str, narrative_id: int, limit: int = 10) -> list[dict]:
    conn = get_connection(db_path)
    rows = conn.execute(
        """SELECT a.headline, a.source, a.url, a.published_at,
                  aa.sentiment_score, aa.sentiment_label
           FROM articles a
           JOIN article_analysis aa ON aa.article_id = a.id
           WHERE aa.narrative_id = ?
           ORDER BY a.published_at DESC
           LIMIT ?""",
        (narrative_id, limit),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]
