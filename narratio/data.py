"""Data access layer — returns dicts/DataFrames from SQLite for the API."""

import logging
from collections import defaultdict
from datetime import datetime, timedelta
import pandas as pd
from narratio.db import connection

logger = logging.getLogger(__name__)


def _score_narrative(weeks: list, reference_date: datetime, four_weeks_ago: str) -> float:
    """Compute significance score for a narrative from its weekly data.

    Score balances magnitude, recency, anomaly, and freshness:
    - 0.3 * cumulative share (total importance)
    - 0.4 * recent share (current relevance, last 4 weeks)
    - 0.2 * peak z-score (anomalous spikes)
    - 0.1 * recency (penalize dormant narratives)
    """
    shares = [w["share_of_attention"] or 0 for w in weeks]
    z_scores = [max(-10, min(10, w["z_score"] or 0)) for w in weeks]

    cum_share = sum(shares)

    recent = [w for w in weeks if w["week_start"] >= four_weeks_ago]
    recent_shares = [w["share_of_attention"] or 0 for w in recent]
    recent_share = sum(recent_shares) / len(recent_shares) if recent_shares else 0

    peak_z = max(abs(z) for z in z_scores) if z_scores else 0

    last_seen = weeks[-1]["week_start"]
    weeks_since_last = (reference_date - datetime.fromisoformat(last_seen)).days / 7
    recency = max(0, 1 - weeks_since_last / 12)

    norm_cum = min(cum_share / 100, 1.0)
    norm_recent = min(recent_share / 100, 1.0)
    norm_z = min(peak_z / 5, 1.0)
    return 0.3 * norm_cum + 0.4 * norm_recent + 0.2 * norm_z + 0.1 * recency


def get_narratives_df(db_path: str) -> pd.DataFrame:
    with connection(db_path) as conn:
        return pd.read_sql_query(
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


def compute_significance_scores(db_path: str) -> int:
    """Compute and store significance scores for all narratives."""
    with connection(db_path) as conn:
        narratives = conn.execute("SELECT id FROM narratives").fetchall()
        if not narratives:
            return 0

        latest = conn.execute("SELECT MAX(week_start) as latest FROM narrative_weeks").fetchone()
        if not latest or not latest["latest"]:
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
            weeks = weeks_by_narrative.get(row["id"], [])
            if not weeks:
                continue
            score = _score_narrative(weeks, current_date, four_weeks_ago)
            updates.append((round(score, 3), row["id"]))
            count += 1

        conn.executemany("UPDATE narratives SET significance_score = ? WHERE id = ?", updates)
        conn.commit()
        return count


def get_top_narrative_ids(db_path: str, top_n: int = 12) -> list[int]:
    """Return the top_n narrative IDs by significance_score."""
    with connection(db_path) as conn:
        rows = conn.execute(
            """SELECT id FROM narratives
               WHERE significance_score IS NOT NULL AND status = 'active'
               ORDER BY significance_score DESC
               LIMIT ?""",
            (top_n,),
        ).fetchall()
        return [r["id"] for r in rows]


def get_top_narrative_ids_for_window(
    db_path: str,
    top_n: int = 12,
    start: str | None = None,
    end: str | None = None,
) -> list[int]:
    """Return top_n narrative IDs ranked by significance within a time window."""
    if not start and not end:
        return get_top_narrative_ids(db_path, top_n)

    with connection(db_path) as conn:
        # Build date filter for narrative_weeks
        date_filter = ""
        date_params: list = []
        if start:
            date_filter += " AND nw.week_start >= ?"
            date_params.append(start)
        if end:
            date_filter += " AND nw.week_start <= ?"
            date_params.append(end)

        rows = conn.execute(
            f"""SELECT nw.narrative_id, nw.week_start,
                       nw.share_of_attention, nw.z_score
                FROM narrative_weeks nw
                JOIN narratives n ON n.id = nw.narrative_id
                WHERE n.status = 'active'{date_filter}
                ORDER BY nw.narrative_id, nw.week_start""",
            date_params,
        ).fetchall()

    if not rows:
        return get_top_narrative_ids(db_path, top_n)

    # Determine window end date for recency calculation
    window_end = datetime.fromisoformat(end) if end else max(
        datetime.fromisoformat(r["week_start"]) for r in rows
    )
    four_weeks_before_end = (window_end - timedelta(weeks=4)).strftime("%Y-%m-%d")

    by_narrative: dict[int, list] = defaultdict(list)
    for r in rows:
        by_narrative[r["narrative_id"]].append(r)

    scores: list[tuple[int, float]] = []
    for nid, weeks in by_narrative.items():
        if sum(w["share_of_attention"] or 0 for w in weeks) == 0:
            continue
        score = _score_narrative(weeks, window_end, four_weeks_before_end)
        scores.append((nid, score))

    scores.sort(key=lambda x: x[1], reverse=True)
    return [nid for nid, _ in scores[:top_n]]


def get_timeline_with_other(
    db_path: str,
    top_n: int = 12,
    start: str | None = None,
    end: str | None = None,
) -> pd.DataFrame:
    """Return timeline data for top_n narratives + an 'Other' bucket."""
    top_ids = get_top_narrative_ids_for_window(db_path, top_n, start, end)
    if not top_ids:
        return pd.DataFrame()

    with connection(db_path) as conn:
        placeholders = ",".join("?" * len(top_ids))

        date_filter = ""
        date_params: list = []
        if start:
            date_filter += " AND nw.week_start >= ?"
            date_params.append(start)
        if end:
            date_filter += " AND nw.week_start <= ?"
            date_params.append(end)

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

    if not df.empty:
        df["week_start"] = pd.to_datetime(df["week_start"])
    return df


def get_timeline_df(db_path: str) -> pd.DataFrame:
    """Legacy: returns all timeline data without top-N filtering."""
    with connection(db_path) as conn:
        df = pd.read_sql_query(
            """SELECT nw.narrative_id, n.label, nw.week_start,
                      nw.article_count, nw.share_of_attention,
                      nw.z_score, nw.sentiment_mean
               FROM narrative_weeks nw
               JOIN narratives n ON n.id = nw.narrative_id
               ORDER BY nw.week_start, nw.share_of_attention DESC""",
            conn,
        )
    if df.empty:
        return df
    df["week_start"] = pd.to_datetime(df["week_start"])
    return df


def get_articles_paginated(
    db_path: str,
    page: int = 1,
    per_page: int = 50,
    source: str | None = None,
    search: str | None = None,
) -> dict:
    with connection(db_path) as conn:
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
        return {
            "articles": [dict(r) for r in rows],
            "total": total,
            "page": page,
            "per_page": per_page,
        }


def get_stats(db_path: str) -> dict:
    with connection(db_path) as conn:
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

        sources_breakdown = [
            dict(r)
            for r in conn.execute(
                """SELECT source, COUNT(*) as count,
                          MIN(published_at) as first_article,
                          MAX(published_at) as last_article
                   FROM articles
                   GROUP BY source
                   ORDER BY count DESC"""
            ).fetchall()
        ]

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
        "sources_breakdown": sources_breakdown,
    }


def get_arising(db_path: str, lookback_weeks: int = 12, min_articles: int = 30, top_n: int = 15) -> list[dict]:
    """Return narratives with rising momentum, ranked by arising score.

    Uses a trailing window (default 12 weeks) to detect narratives
    whose relative importance is growing, regardless of overall volume changes.
    """
    with connection(db_path) as conn:
        latest_row = conn.execute("SELECT MAX(week_start) as latest FROM narrative_weeks").fetchone()
        if not latest_row or not latest_row["latest"]:
            return []
        latest_date = datetime.fromisoformat(latest_row["latest"])
        window_start = (latest_date - timedelta(weeks=lookback_weeks)).strftime("%Y-%m-%d")

        week_rows = conn.execute(
            """SELECT nw.narrative_id, nw.week_start, nw.article_count, nw.share_of_attention
               FROM narrative_weeks nw
               WHERE nw.week_start >= ?
               ORDER BY nw.narrative_id, nw.week_start""",
            (window_start,),
        ).fetchall()

        narr_rows = conn.execute(
            "SELECT id, label, first_seen, status FROM narratives",
        ).fetchall()
        narr_meta = {r["id"]: dict(r) for r in narr_rows}

        top_ids = {r["id"] for r in conn.execute(
            """SELECT id FROM narratives
               WHERE significance_score IS NOT NULL AND status = 'active'
               ORDER BY significance_score DESC LIMIT 10"""
        ).fetchall()}

        max_share_row = conn.execute(
            "SELECT MAX(share_of_attention) as ms FROM narrative_weeks WHERE week_start = ?",
            (latest_row["latest"],),
        ).fetchone()
        max_share = max_share_row["ms"] if max_share_row and max_share_row["ms"] else 1.0

    by_narrative: dict[int, list] = defaultdict(list)
    for r in week_rows:
        by_narrative[r["narrative_id"]].append(r)

    results = []
    for nid, weeks in by_narrative.items():
        if nid not in narr_meta or nid in top_ids:
            continue

        weeks_sorted = sorted(weeks, key=lambda w: w["week_start"])
        article_counts = [w["article_count"] or 0 for w in weeks_sorted]
        shares = [w["share_of_attention"] or 0 for w in weeks_sorted]

        total_articles_in_window = sum(article_counts)
        if total_articles_in_window < min_articles:
            continue

        latest_share = shares[-1]
        latest_articles = article_counts[-1]
        n_weeks = len(shares)

        # Momentum: slope of share_of_attention over recent weeks (last 6)
        momentum_weeks = 6
        recent_shares = shares[-momentum_weeks:] if len(shares) >= momentum_weeks else shares
        n_momentum = len(recent_shares)
        if n_momentum >= 2:
            x_mean = (n_momentum - 1) / 2
            y_mean = sum(recent_shares) / n_momentum
            numerator = sum((i - x_mean) * (y - y_mean) for i, y in enumerate(recent_shares))
            denominator = sum((i - x_mean) ** 2 for i in range(n_momentum))
            slope = numerator / denominator if denominator > 0 else 0
        else:
            slope = 0

        if slope < -0.3:
            continue

        growth_velocity = max(min(slope / 0.5, 1.0), 0.0)
        current_strength = min(latest_share / max_share, 1.0) if max_share > 0 else 0
        consistency = min(n_weeks / lookback_weeks, 1.0)

        mid = max(1, len(shares) // 2)
        recent_max = max(shares[-mid:]) if shares[-mid:] else 0
        older_max = max(shares[:mid]) if shares[:mid] else 0
        recent_peak = min(recent_max / older_max, 2.0) / 2.0 if older_max > 0 else (0.5 if recent_max > 0 else 0)

        arising_score = (
            0.35 * growth_velocity
            + 0.25 * current_strength
            + 0.25 * recent_peak
            + 0.15 * consistency
        )

        if slope > 0.1:
            growth_trend = "accelerating"
        elif slope > -0.1:
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


def get_narrative_detail(db_path: str, narrative_id: int) -> dict | None:
    with connection(db_path) as conn:
        narrative = conn.execute("SELECT * FROM narratives WHERE id = ?", (narrative_id,)).fetchone()
        if narrative is None:
            return None
        weeks = conn.execute(
            "SELECT * FROM narrative_weeks WHERE narrative_id = ? ORDER BY week_start",
            (narrative_id,),
        ).fetchall()
        return {
            "id": narrative["id"],
            "label": narrative["label"],
            "first_seen": narrative["first_seen"],
            "last_seen": narrative["last_seen"],
            "status": narrative["status"],
            "significance_score": narrative["significance_score"],
            "weeks": [dict(w) for w in weeks],
        }


def get_map_data(db_path: str, start: str | None = None, end: str | None = None) -> list[dict]:
    """Return per-country aggregation with top 3 narratives for map visualization."""
    with connection(db_path) as conn:
        # Check table exists
        tables = [r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='article_countries'"
        ).fetchall()]
        if "article_countries" not in tables:
            return []

        date_filter = ""
        params: list = []
        if start:
            date_filter += " AND a.published_at >= ?"
            params.append(start)
        if end:
            date_filter += " AND a.published_at <= ?"
            params.append(end)

        # Total articles in range for share calculation
        total_row = conn.execute(
            f"SELECT COUNT(DISTINCT ac.article_id) FROM article_countries ac JOIN articles a ON a.id = ac.article_id WHERE 1=1{date_filter}",
            params,
        ).fetchone()
        total = total_row[0] if total_row else 0
        if total == 0:
            return []

        # Per-country counts
        country_rows = conn.execute(
            f"""SELECT ac.country_code, COUNT(DISTINCT ac.article_id) as article_count
                FROM article_countries ac
                JOIN articles a ON a.id = ac.article_id
                WHERE 1=1{date_filter}
                GROUP BY ac.country_code
                ORDER BY article_count DESC""",
            params,
        ).fetchall()

        # Top 3 narratives per country
        narr_rows = conn.execute(
            f"""SELECT country_code, narrative_id, label, narr_count FROM (
                    SELECT ac.country_code, aa.narrative_id, n.label,
                           COUNT(*) as narr_count,
                           ROW_NUMBER() OVER (PARTITION BY ac.country_code ORDER BY COUNT(*) DESC) as rn
                    FROM article_countries ac
                    JOIN articles a ON a.id = ac.article_id
                    JOIN article_analysis aa ON aa.article_id = ac.article_id
                    JOIN narratives n ON n.id = aa.narrative_id
                    WHERE aa.narrative_id IS NOT NULL{date_filter}
                    GROUP BY ac.country_code, aa.narrative_id
                ) WHERE rn <= 3""",
            params,
        ).fetchall()

        narr_by_country: dict[str, list[dict]] = {}
        for r in narr_rows:
            code = r["country_code"]
            narr_by_country.setdefault(code, []).append({
                "narrative_id": r["narrative_id"],
                "label": r["label"],
                "count": r["narr_count"],
            })

        from narratio.countries import COUNTRY_NAMES
        result = []
        for r in country_rows:
            code = r["country_code"]
            result.append({
                "country_code": code,
                "country_name": COUNTRY_NAMES.get(code, code),
                "article_count": r["article_count"],
                "share": round(r["article_count"] / total * 100, 1),
                "top_narratives": narr_by_country.get(code, []),
            })
        return result


def get_article_date_range(db_path: str) -> dict:
    """Return min/max published_at dates for the time filter UI."""
    with connection(db_path) as conn:
        row = conn.execute(
            "SELECT MIN(published_at) as min_date, MAX(published_at) as max_date FROM articles"
        ).fetchone()
        return {
            "min_date": row["min_date"] if row else None,
            "max_date": row["max_date"] if row else None,
        }


def get_narrative_headlines(db_path: str, narrative_id: int, limit: int = 10) -> list[dict]:
    with connection(db_path) as conn:
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
        return [dict(r) for r in rows]
