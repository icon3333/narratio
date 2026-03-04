"""Weekly narrative summarization and analytics computation."""

import asyncio
import json
import logging
from datetime import datetime, timedelta
import httpx
from narratio.db import get_connection

logger = logging.getLogger(__name__)

OPENROUTER_CHAT_URL = "https://openrouter.ai/api/v1/chat/completions"

MAX_RETRIES = 5
BACKOFF_BASE = 2  # seconds


async def _call_openrouter_chat_async(
    client: httpx.AsyncClient,
    messages: list[dict],
    api_key: str,
    model: str = "anthropic/claude-sonnet-4",
) -> dict:
    for attempt in range(MAX_RETRIES):
        resp = await client.post(
            OPENROUTER_CHAT_URL,
            json={"model": model, "messages": messages, "temperature": 0.3},
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            timeout=120,
        )
        if resp.status_code == 429:
            wait = min(BACKOFF_BASE ** (attempt + 1), 32)
            logger.warning("Summary API rate limited, retrying in %ds (attempt %d/%d)", wait, attempt + 1, MAX_RETRIES)
            await asyncio.sleep(wait)
            continue
        resp.raise_for_status()
        return resp.json()
    raise RuntimeError(f"OpenRouter API rate limited after {MAX_RETRIES} retries")


def _week_start(published_at: str) -> str:
    dt = datetime.fromisoformat(published_at.replace("+0000", "+00:00"))
    monday = dt - timedelta(days=dt.weekday())
    return monday.strftime("%Y-%m-%d")


def compute_weekly_analytics(db_path: str, z_score_window: int = 8) -> int:
    """Compute and persist weekly analytics for all narratives.

    No LLM calls, no API key needed. Writes narrative_weeks rows with
    summary=NULL for new rows. Existing summaries are preserved.
    Fast, deterministic, idempotent.

    Returns the number of narrative-week rows written/updated.
    """
    conn = get_connection(db_path)

    narratives = conn.execute("SELECT id, label FROM narratives").fetchall()
    if not narratives:
        logger.info("No narratives to compute analytics for")
        conn.close()
        return 0
    logger.info("Computing weekly analytics for %d narratives", len(narratives))

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

    # Write weekly_totals
    for ws in weekly_article_counts:
        noise = weekly_article_counts[ws] - weekly_clustered_counts.get(ws, 0)
        conn.execute(
            """INSERT OR REPLACE INTO weekly_totals (week_start, total_articles, total_clustered, total_noise)
               VALUES (?, ?, ?, ?)""",
            (ws, weekly_article_counts[ws], weekly_clustered_counts.get(ws, 0), noise),
        )
    conn.commit()

    # Write ALL narrative_weeks rows — analytics decoupled from LLM
    total_weeks_processed = 0
    for narrative in narratives:
        nid = narrative["id"]
        weeks_data = buckets.get(nid, {})

        for ws, articles in sorted(weeks_data.items()):
            article_count = len(articles)
            # Use clustered count as denominator (not total including noise)
            clustered_total = weekly_clustered_counts.get(ws, 0)
            if clustered_total == 0:
                continue  # skip weeks with no clustered articles
            share = (article_count / clustered_total) * 100

            sentiments = [a["sentiment_score"] for a in articles if a["sentiment_score"] is not None]
            sentiment_mean = sum(sentiments) / len(sentiments) if sentiments else 0.0

            top_ids = json.dumps([a["id"] for a in articles[:5]])

            # Preserve existing summary if present
            existing = conn.execute(
                "SELECT summary FROM narrative_weeks WHERE narrative_id = ? AND week_start = ?",
                (nid, ws),
            ).fetchone()
            existing_summary = existing["summary"] if existing else None

            conn.execute(
                """INSERT OR REPLACE INTO narrative_weeks
                   (narrative_id, week_start, article_count, share_of_attention,
                    sentiment_mean, summary, top_headline_ids)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (nid, ws, article_count, round(share, 2), round(sentiment_mean, 3),
                 existing_summary, top_ids),
            )
            total_weeks_processed += 1

    conn.commit()

    _compute_z_scores(conn, window=z_score_window)
    conn.commit()
    conn.close()
    logger.info("Analytics complete: %d narrative-weeks computed", total_weeks_processed)
    return total_weeks_processed


async def _summarize_one(
    client: httpx.AsyncClient,
    semaphore: asyncio.Semaphore,
    api_key: str,
    nid: int,
    label: str,
    ws: str,
    headlines: list[str],
    model: str = "anthropic/claude-sonnet-4",
) -> tuple[int, str, str]:
    """Summarize a single narrative-week. Returns (narrative_id, week_start, summary)."""
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

    async with semaphore:
        result = await _call_openrouter_chat_async(client, messages, api_key, model=model)

    summary = result["choices"][0]["message"]["content"].strip()
    return (nid, ws, summary)


async def _generate_summaries_async(
    db_path: str,
    api_key: str,
    max_concurrent: int = 5,
    top_n: int | None = None,
    model: str = "anthropic/claude-sonnet-4",
) -> int:
    """Generate LLM summaries for narrative_weeks rows where summary IS NULL.

    If top_n is set, only generate summaries for the top_n narratives by
    total article count (cost optimization).
    """
    conn = get_connection(db_path)

    # Find rows needing summaries
    query = """
        SELECT nw.narrative_id, n.label, nw.week_start
        FROM narrative_weeks nw
        JOIN narratives n ON n.id = nw.narrative_id
        WHERE nw.summary IS NULL
    """
    if top_n is not None:
        query += f"""
            AND nw.narrative_id IN (
                SELECT narrative_id FROM narrative_weeks
                GROUP BY narrative_id
                ORDER BY SUM(article_count) DESC
                LIMIT {top_n}
            )
        """

    pending_rows = conn.execute(query).fetchall()
    if not pending_rows:
        logger.info("No narrative-weeks need summaries")
        conn.close()
        return 0
    logger.info("Generating summaries for %d narrative-weeks", len(pending_rows))

    # Get headlines for each pending (nid, ws) pair
    pending_summaries = []
    for row in pending_rows:
        nid = row["narrative_id"]
        label = row["label"]
        ws = row["week_start"]

        articles = conn.execute(
            """SELECT a.headline FROM articles a
               JOIN article_analysis aa ON aa.article_id = a.id
               WHERE aa.narrative_id = ? AND a.published_at >= ? AND a.published_at < ?
               LIMIT 10""",
            (nid, ws, (datetime.fromisoformat(ws) + timedelta(days=7)).strftime("%Y-%m-%d")),
        ).fetchall()

        headlines = [a["headline"] for a in articles]
        if headlines:
            pending_summaries.append((nid, label, ws, headlines))

    conn.close()

    if not pending_summaries:
        return 0

    # Run LLM calls concurrently
    summaries: dict[tuple[int, str], str] = {}
    semaphore = asyncio.Semaphore(max_concurrent)
    async with httpx.AsyncClient() as client:
        tasks = [
            _summarize_one(client, semaphore, api_key, nid, label, ws, headlines, model=model)
            for nid, label, ws, headlines in pending_summaries
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

    for result in results:
        if isinstance(result, Exception):
            logger.error("Summary generation failed: %s", result)
            continue
        nid, ws, summary = result
        summaries[(nid, ws)] = summary

    # Update rows with summaries
    conn = get_connection(db_path)
    count = 0
    for (nid, ws), summary in summaries.items():
        conn.execute(
            "UPDATE narrative_weeks SET summary = ? WHERE narrative_id = ? AND week_start = ?",
            (summary, nid, ws),
        )
        count += 1

    conn.commit()
    conn.close()
    logger.info("Summary generation complete: %d summaries written", count)
    return count


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
            # Lookback window: use preceding weeks to compute baseline, then
            # measure how anomalous the current week is relative to that baseline
            start = max(0, i - window)
            window_shares = shares[start:i + 1]

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


def generate_weekly_summaries(
    db_path: str,
    api_key: str,
    top_n: int | None = None,
    model: str = "anthropic/claude-sonnet-4",
) -> int:
    """Generate LLM summaries for narrative_weeks rows missing summaries."""
    return asyncio.run(_generate_summaries_async(db_path, api_key, top_n=top_n, model=model))


# Legacy entrypoint — calls both analytics + summaries for backward compat
def summarize_narratives(db_path: str, api_key: str) -> int:
    weeks = compute_weekly_analytics(db_path)
    generate_weekly_summaries(db_path, api_key)
    return weeks
