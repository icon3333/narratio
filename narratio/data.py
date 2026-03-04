"""Data access layer — returns dicts/DataFrames from SQLite for the API."""

import logging
from collections import defaultdict
from datetime import datetime, timedelta
import pandas as pd
from narratio.db import get_connection

logger = logging.getLogger(__name__)


def get_narratives_df(db_path: str) -> pd.DataFrame:
    conn = get_connection(db_path)
    df = pd.read_sql_query(
        """SELECT n.id, n.label, n.first_seen, n.last_seen, n.status,
                  n.significance_score,
                  COUNT(aa.article_id) as article_count
           FROM narratives n
           LEFT JOIN article_analysis aa ON aa.narrative_id = n.id
           WHERE n.status = 'active'
           GROUP BY n.id
           HAVING article_count > 0
           ORDER BY CASE WHEN n.significance_score IS NULL THEN 1 ELSE 0 END,
                  n.significance_score DESC, article_count DESC""",
        conn,
    )
    conn.close()
    return df


def compute_significance_scores(db_path: str) -> int:
    """Compute and store significance scores for all narratives.

    Score balances magnitude, recency, anomaly, and freshness:
    - 0.3 * cumulative share (total importance)
    - 0.4 * recent share (current relevance, last 4 weeks)
    - 0.2 * peak z-score (anomalous spikes)
    - 0.1 * recency (penalize dormant narratives)

    Returns number of narratives scored.
    """
    conn = get_connection(db_path)

    narratives = conn.execute("SELECT id FROM narratives").fetchall()
    if not narratives:
        conn.close()
        return 0

    # Get current date from the latest week_start in the data
    latest = conn.execute("SELECT MAX(week_start) as latest FROM narrative_weeks").fetchone()
    if not latest or not latest["latest"]:
        conn.close()
        return 0
    current_date = datetime.fromisoformat(latest["latest"])
    four_weeks_ago = (current_date - timedelta(weeks=4)).strftime("%Y-%m-%d")

    # Batch fetch all narrative weeks in one query (avoids N+1)
    all_weeks = conn.execute(
        "SELECT narrative_id, week_start, share_of_attention, z_score FROM narrative_weeks ORDER BY narrative_id, week_start"
    ).fetchall()
    weeks_by_narrative: dict[int, list] = {}
    for w in all_weeks:
        weeks_by_narrative.setdefault(w["narrative_id"], []).append(w)

    count = 0
    updates = []
    for row in narratives:
        nid = row["id"]
        weeks = weeks_by_narrative.get(nid, [])

        if not weeks:
            continue  # leave significance_score as NULL

        shares = [w["share_of_attention"] or 0 for w in weeks]
        # Clamp extreme z_scores (data corruption guard)
        z_scores = [max(-10, min(10, w["z_score"] or 0)) for w in weeks]

        cum_share = sum(shares)

        recent = [w for w in weeks if w["week_start"] >= four_weeks_ago]
        recent_shares = [w["share_of_attention"] or 0 for w in recent]
        recent_share = sum(recent_shares) / len(recent_shares) if recent_shares else 0

        peak_z = max(abs(z) for z in z_scores) if z_scores else 0

        last_seen = weeks[-1]["week_start"]
        weeks_since_last = (current_date - datetime.fromisoformat(last_seen)).days / 7
        recency = max(0, 1 - weeks_since_last / 12)

        norm_cum = min(cum_share / 100, 1.0)
        norm_recent = min(recent_share / 100, 1.0)
        norm_z = min(peak_z / 5, 1.0)
        score = 0.3 * norm_cum + 0.4 * norm_recent + 0.2 * norm_z + 0.1 * recency

        updates.append((round(score, 3), nid))
        count += 1

    conn.executemany("UPDATE narratives SET significance_score = ? WHERE id = ?", updates)

    conn.commit()
    conn.close()
    return count


def get_top_narrative_ids(db_path: str, top_n: int = 12) -> list[int]:
    """Return the top_n narrative IDs by significance_score."""
    conn = get_connection(db_path)
    rows = conn.execute(
        """SELECT id FROM narratives
           WHERE significance_score IS NOT NULL AND status = 'active'
           ORDER BY significance_score DESC
           LIMIT ?""",
        (top_n,),
    ).fetchall()
    conn.close()
    return [r["id"] for r in rows]


def get_top_narrative_ids_for_window(
    db_path: str,
    top_n: int = 12,
    start: str | None = None,
    end: str | None = None,
) -> list[int]:
    """Return top_n narrative IDs ranked by significance within a time window.

    When start/end are None, falls back to global significance_score.
    When a window is specified, computes window-relative scores:
    - 0.3 * cumulative share (within window)
    - 0.4 * recent share (last 4 weeks relative to window end)
    - 0.2 * peak z-score (within window)
    - 0.1 * recency (relative to window end)
    """
    if not start and not end:
        return get_top_narrative_ids(db_path, top_n)

    conn = get_connection(db_path)

    # Build date filter for narrative_weeks
    date_filter = ""
    date_params: list = []
    if start:
        date_filter += " AND nw.week_start >= ?"
        date_params.append(start)
    if end:
        date_filter += " AND nw.week_start <= ?"
        date_params.append(end)

    # Get all narrative weeks within the window (active narratives only)
    rows = conn.execute(
        f"""SELECT nw.narrative_id, nw.week_start,
                   nw.share_of_attention, nw.z_score
            FROM narrative_weeks nw
            JOIN narratives n ON n.id = nw.narrative_id
            WHERE n.status = 'active'{date_filter}
            ORDER BY nw.narrative_id, nw.week_start""",
        date_params,
    ).fetchall()
    conn.close()

    if not rows:
        return get_top_narrative_ids(db_path, top_n)

    # Determine window end date for recency calculation
    window_end = datetime.fromisoformat(end) if end else max(
        datetime.fromisoformat(r["week_start"]) for r in rows
    )
    four_weeks_before_end = (window_end - timedelta(weeks=4)).strftime("%Y-%m-%d")

    # Group by narrative
    by_narrative: dict[int, list] = defaultdict(list)
    for r in rows:
        by_narrative[r["narrative_id"]].append(r)

    scores: list[tuple[int, float]] = []
    for nid, weeks in by_narrative.items():
        shares = [w["share_of_attention"] or 0 for w in weeks]
        # Clamp extreme z_scores (data corruption guard)
        z_scores = [max(-10, min(10, w["z_score"] or 0)) for w in weeks]

        cum_share = sum(shares)
        if cum_share == 0:
            continue  # skip narratives with zero activity in window

        recent = [w for w in weeks if w["week_start"] >= four_weeks_before_end]
        recent_shares = [w["share_of_attention"] or 0 for w in recent]
        recent_share = sum(recent_shares) / len(recent_shares) if recent_shares else 0

        peak_z = max(abs(z) for z in z_scores) if z_scores else 0

        last_seen = weeks[-1]["week_start"]
        weeks_since_last = (window_end - datetime.fromisoformat(last_seen)).days / 7
        recency = max(0, 1 - weeks_since_last / 12)

        norm_cum = min(cum_share / 100, 1.0)
        norm_recent = min(recent_share / 100, 1.0)
        norm_z = min(peak_z / 5, 1.0)
        score = 0.3 * norm_cum + 0.4 * norm_recent + 0.2 * norm_z + 0.1 * recency

        scores.append((nid, score))

    scores.sort(key=lambda x: x[1], reverse=True)
    return [nid for nid, _ in scores[:top_n]]


def get_timeline_with_other(
    db_path: str,
    top_n: int = 12,
    start: str | None = None,
    end: str | None = None,
) -> pd.DataFrame:
    """Return timeline data for top_n narratives + an 'Other' bucket.

    The 'Other' row aggregates all non-top-N narratives per week.
    """
    conn = get_connection(db_path)

    # Get top narrative IDs (window-aware when date filters are specified)
    top_ids = get_top_narrative_ids_for_window(db_path, top_n, start, end)
    if not top_ids:
        conn.close()
        return pd.DataFrame()

    placeholders = ",".join("?" * len(top_ids))

    # Build date filter
    date_filter = ""
    date_params: list = []
    if start:
        date_filter += " AND nw.week_start >= ?"
        date_params.append(start)
    if end:
        date_filter += " AND nw.week_start <= ?"
        date_params.append(end)

    # Single query: top-N rows returned individually, rest aggregated as "Other"
    df = pd.read_sql_query(
        f"""SELECT nw.narrative_id, n.label, nw.week_start,
                   nw.article_count, nw.share_of_attention,
                   nw.z_score, nw.sentiment_mean
            FROM narrative_weeks nw
            JOIN narratives n ON n.id = nw.narrative_id
            WHERE nw.narrative_id IN ({placeholders}){date_filter}
        UNION ALL
        SELECT
                -1 as narrative_id,
                'Other' as label,
                nw.week_start,
                SUM(nw.article_count) as article_count,
                SUM(nw.share_of_attention) as share_of_attention,
                NULL as z_score,
                AVG(nw.sentiment_mean) as sentiment_mean
            FROM narrative_weeks nw
            WHERE nw.narrative_id NOT IN ({placeholders}){date_filter}
            GROUP BY nw.week_start
            HAVING SUM(nw.article_count) > 0
        ORDER BY week_start, share_of_attention DESC""",
        conn,
        params=top_ids + date_params + top_ids + date_params,
    )

    conn.close()

    result = df
    if not result.empty:
        result["week_start"] = pd.to_datetime(result["week_start"])
    return result


def get_timeline_df(db_path: str) -> pd.DataFrame:
    """Legacy: returns all timeline data without top-N filtering."""
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


def get_articles_paginated(
    db_path: str,
    page: int = 1,
    per_page: int = 50,
    source: str | None = None,
    search: str | None = None,
) -> dict:
    conn = get_connection(db_path)
    where_clauses = []
    params: list = []
    if source:
        where_clauses.append("a.source = ?")
        params.append(source)
    if search:
        where_clauses.append("a.headline LIKE ?")
        params.append(f"%{search}%")
    where_sql = (" WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

    total = conn.execute(
        f"SELECT COUNT(*) as cnt FROM articles a{where_sql}", params
    ).fetchone()["cnt"]

    offset = (page - 1) * per_page
    rows = conn.execute(
        f"""SELECT a.headline, a.source, a.url, a.published_at
            FROM articles a{where_sql}
            ORDER BY a.published_at DESC
            LIMIT ? OFFSET ?""",
        params + [per_page, offset],
    ).fetchall()
    conn.close()
    return {
        "articles": [dict(r) for r in rows],
        "total": total,
        "page": page,
        "per_page": per_page,
    }


def get_stats(db_path: str) -> dict:
    conn = get_connection(db_path)

    # Consolidated counts in a single query using CTEs
    counts = conn.execute(
        """SELECT
               (SELECT COUNT(*) FROM articles) as total_articles,
               (SELECT COUNT(*) FROM narratives) as total_narratives,
               (SELECT COUNT(*) FROM narratives WHERE status='active') as active_narratives,
               (SELECT COUNT(*) FROM narratives WHERE status='dormant') as dormant_narratives,
               (SELECT MIN(published_at) FROM articles) as first_article_date,
               (SELECT MAX(published_at) FROM articles) as last_article_date,
               (SELECT COUNT(*) FROM articles a LEFT JOIN article_analysis aa ON aa.article_id = a.id WHERE aa.narrative_id IS NULL) as noise_count"""
    ).fetchone()

    top_by_significance = [
        dict(r)
        for r in conn.execute(
            """SELECT id, label, significance_score
               FROM narratives
               WHERE significance_score IS NOT NULL
               ORDER BY significance_score DESC LIMIT 5"""
        ).fetchall()
    ]

    biggest_movers = [
        dict(r)
        for r in conn.execute(
            """SELECT nw.narrative_id as id, n.label, nw.z_score
               FROM narrative_weeks nw
               JOIN narratives n ON n.id = nw.narrative_id
               WHERE nw.week_start = (SELECT MAX(week_start) FROM narrative_weeks)
                 AND nw.z_score IS NOT NULL
               ORDER BY ABS(nw.z_score) DESC LIMIT 5"""
        ).fetchall()
    ]

    longest_running = [
        dict(r)
        for r in conn.execute(
            """SELECT id, label, first_seen, last_seen,
                      CAST(julianday(last_seen) - julianday(first_seen) AS INTEGER) as duration_days
               FROM narratives
               ORDER BY duration_days DESC LIMIT 5"""
        ).fetchall()
    ]

    conn.close()
    return {
        "total_articles": counts["total_articles"],
        "total_narratives": counts["total_narratives"],
        "active_narratives": counts["active_narratives"],
        "dormant_narratives": counts["dormant_narratives"],
        "first_article_date": counts["first_article_date"],
        "last_article_date": counts["last_article_date"],
        "noise_count": counts["noise_count"],
        "top_by_significance": top_by_significance,
        "biggest_movers": biggest_movers,
        "longest_running": longest_running,
    }


def get_arising(db_path: str, lookback_weeks: int = 12, min_articles: int = 50, top_n: int = 15) -> list[dict]:
    """Return narratives with rising momentum, ranked by arising score.

    Uses a trailing window (default 12 weeks ≈ 3 months) to detect narratives
    whose coverage is growing, regardless of when they first appeared.

    Hard filters:
    - ≥ min_articles in the trailing window (default 50)
    - Positive slope (only rising narratives)

    arising_score = 0.40 * growth_velocity   (slope normalized: 5 articles/week = 1.0)
                  + 0.30 * current_strength   (latest share_of_attention, normalized)
                  + 0.30 * consistency         (fraction of window weeks with data)
    """
    conn = get_connection(db_path)

    # Find the latest week in the data
    latest_row = conn.execute("SELECT MAX(week_start) as latest FROM narrative_weeks").fetchone()
    if not latest_row or not latest_row["latest"]:
        conn.close()
        return []
    latest_date = datetime.fromisoformat(latest_row["latest"])
    window_start = (latest_date - timedelta(weeks=lookback_weeks)).strftime("%Y-%m-%d")

    # Get all narratives with their weekly data in the trailing window
    week_rows = conn.execute(
        """SELECT nw.narrative_id, nw.week_start, nw.article_count, nw.share_of_attention
           FROM narrative_weeks nw
           WHERE nw.week_start >= ?
           ORDER BY nw.narrative_id, nw.week_start""",
        (window_start,),
    ).fetchall()

    # Get narrative metadata
    narr_rows = conn.execute(
        "SELECT id, label, first_seen, status FROM narratives",
    ).fetchall()
    narr_meta = {r["id"]: dict(r) for r in narr_rows}

    # Find max share across all narratives in the latest week (for normalization)
    max_share_row = conn.execute(
        "SELECT MAX(share_of_attention) as ms FROM narrative_weeks WHERE week_start = ?",
        (latest_row["latest"],),
    ).fetchone()
    max_share = max_share_row["ms"] if max_share_row and max_share_row["ms"] else 1.0

    conn.close()

    # Group weeks by narrative
    by_narrative: dict[int, list] = defaultdict(list)
    for r in week_rows:
        by_narrative[r["narrative_id"]].append(r)

    results = []
    for nid, weeks in by_narrative.items():
        if nid not in narr_meta:
            continue

        weeks_sorted = sorted(weeks, key=lambda w: w["week_start"])
        article_counts = [w["article_count"] or 0 for w in weeks_sorted]
        shares = [w["share_of_attention"] or 0 for w in weeks_sorted]

        total_articles_in_window = sum(article_counts)
        if total_articles_in_window < min_articles:
            continue

        latest_share = shares[-1]
        latest_articles = article_counts[-1]

        # Growth velocity: linear slope of article_count over weeks, normalized
        n_weeks = len(article_counts)
        if n_weeks >= 2:
            x_mean = (n_weeks - 1) / 2
            y_mean = sum(article_counts) / n_weeks
            numerator = sum((i - x_mean) * (y - y_mean) for i, y in enumerate(article_counts))
            denominator = sum((i - x_mean) ** 2 for i in range(n_weeks))
            slope = numerator / denominator if denominator > 0 else 0
        else:
            slope = 0

        # Hard filter: only rising narratives
        if slope <= 0:
            continue

        # Normalize: slope of 5 articles/week = 1.0
        growth_velocity = min(slope / 5, 1.0)

        # Current strength: latest share normalized by max share
        current_strength = min(latest_share / max_share, 1.0) if max_share > 0 else 0

        # Consistency: fraction of window weeks that have data
        consistency = min(n_weeks / lookback_weeks, 1.0)

        arising_score = (
            0.40 * growth_velocity
            + 0.30 * current_strength
            + 0.30 * consistency
        )

        # Growth trend label from slope
        if slope > 1:
            growth_trend = "accelerating"
        elif slope > 0:
            growth_trend = "steady"
        else:
            growth_trend = "fading"

        meta = narr_meta[nid]
        first_seen = datetime.fromisoformat(meta["first_seen"])
        weeks_since_first = max(1, round((latest_date - first_seen).days / 7))

        results.append({
            "id": nid,
            "label": meta["label"],
            "first_seen": meta["first_seen"],
            "status": meta["status"],
            "arising_score": round(arising_score, 4),
            "latest_share": latest_share,
            "article_count_total": total_articles_in_window,
            "article_count_latest": latest_articles,
            "weeks_active": weeks_since_first,
            "growth_trend": growth_trend,
            "weekly_articles": article_counts,
        })

    results.sort(key=lambda x: x["arising_score"], reverse=True)
    return results[:top_n]


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
        "significance_score": narrative["significance_score"],
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
