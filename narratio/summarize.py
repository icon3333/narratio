"""Weekly narrative summarization and analytics computation."""

import json
from datetime import datetime, timezone, timedelta
import httpx
from narratio.db import get_connection

SUMMARY_MODEL = "anthropic/claude-sonnet-4"
OPENROUTER_CHAT_URL = "https://openrouter.ai/api/v1/chat/completions"


def _call_openrouter_chat(messages: list[dict], api_key: str, model: str = SUMMARY_MODEL) -> dict:
    resp = httpx.post(
        OPENROUTER_CHAT_URL,
        json={"model": model, "messages": messages, "temperature": 0.3},
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        timeout=120,
    )
    resp.raise_for_status()
    return resp.json()


def _week_start(timestamp: int) -> str:
    dt = datetime.fromtimestamp(timestamp, tz=timezone.utc)
    monday = dt - timedelta(days=dt.weekday())
    return monday.strftime("%Y-%m-%d")


def summarize_narratives(db_path: str, api_key: str) -> int:
    conn = get_connection(db_path)

    narratives = conn.execute("SELECT id, label FROM narratives").fetchall()
    if not narratives:
        conn.close()
        return 0

    all_articles = conn.execute(
        """SELECT a.id, a.headline, a.summary, a.published_at,
                  aa.narrative_id, aa.sentiment_score
           FROM articles a
           JOIN article_analysis aa ON aa.article_id = a.id
           WHERE aa.narrative_id IS NOT NULL
           ORDER BY a.published_at"""
    ).fetchall()

    # Build weekly buckets: {narrative_id: {week_start: [articles]}}
    buckets: dict[int, dict[str, list]] = {}
    weekly_article_counts: dict[str, int] = {}
    weekly_clustered_counts: dict[str, int] = {}

    for a in all_articles:
        nid = a["narrative_id"]
        ws = _week_start(a["published_at"])
        buckets.setdefault(nid, {}).setdefault(ws, []).append(a)
        weekly_clustered_counts[ws] = weekly_clustered_counts.get(ws, 0) + 1

    total_articles = conn.execute(
        "SELECT published_at FROM articles ORDER BY published_at"
    ).fetchall()
    for a in total_articles:
        ws = _week_start(a["published_at"])
        weekly_article_counts[ws] = weekly_article_counts.get(ws, 0) + 1

    for ws in weekly_article_counts:
        noise = weekly_article_counts[ws] - weekly_clustered_counts.get(ws, 0)
        conn.execute(
            """INSERT OR REPLACE INTO weekly_totals (week_start, total_articles, total_clustered, total_noise)
               VALUES (?, ?, ?, ?)""",
            (ws, weekly_article_counts[ws], weekly_clustered_counts.get(ws, 0), noise),
        )
    conn.commit()

    total_weeks_processed = 0

    for narrative in narratives:
        nid = narrative["id"]
        label = narrative["label"]
        weeks_data = buckets.get(nid, {})

        for ws, articles in sorted(weeks_data.items()):
            article_count = len(articles)
            total_week = weekly_article_counts.get(ws, 1)
            share = (article_count / total_week) * 100

            sentiments = [a["sentiment_score"] for a in articles if a["sentiment_score"] is not None]
            sentiment_mean = sum(sentiments) / len(sentiments) if sentiments else 0.0

            headlines = [a["headline"] for a in articles[:10]]
            top_ids = json.dumps([a["id"] for a in articles[:5]])

            headlines_text = "\n".join(f"- {h}" for h in headlines)
            messages = [
                {
                    "role": "user",
                    "content": f"""Summarize this week's development for the "{label}" narrative in 1-2 sentences.
Focus on what changed or what's new this week.

Headlines from week of {ws}:
{headlines_text}""",
                }
            ]

            result = _call_openrouter_chat(messages, api_key)
            summary = result["choices"][0]["message"]["content"].strip()

            conn.execute(
                """INSERT OR REPLACE INTO narrative_weeks
                   (narrative_id, week_start, article_count, share_of_attention,
                    sentiment_mean, summary, top_headline_ids)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (nid, ws, article_count, round(share, 2), round(sentiment_mean, 3), summary, top_ids),
            )
            total_weeks_processed += 1

        conn.commit()

    _compute_z_scores(conn)
    conn.commit()
    conn.close()
    return total_weeks_processed


def _compute_z_scores(conn, window: int = 8):
    """Compute z-scores for share_of_attention across full history."""
    narratives = conn.execute("SELECT DISTINCT narrative_id FROM narrative_weeks").fetchall()

    for row in narratives:
        nid = row["narrative_id"]
        weeks = conn.execute(
            "SELECT week_start, share_of_attention FROM narrative_weeks WHERE narrative_id = ? ORDER BY week_start",
            (nid,),
        ).fetchall()

        shares = [w["share_of_attention"] for w in weeks]
        week_starts = [w["week_start"] for w in weeks]

        for i, (ws, share) in enumerate(zip(week_starts, shares)):
            start = max(0, i - window)
            window_shares = shares[start:i] if i > 0 else shares[:1]

            if len(window_shares) < 2:
                z = 0.0
            else:
                mean = sum(window_shares) / len(window_shares)
                std = (sum((s - mean) ** 2 for s in window_shares) / len(window_shares)) ** 0.5
                z = (share - mean) / std if std > 0 else 0.0

            conn.execute(
                "UPDATE narrative_weeks SET z_score = ? WHERE narrative_id = ? AND week_start = ?",
                (round(z, 3), nid, ws),
            )
