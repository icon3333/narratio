"""Sentiment analysis via OpenRouter (Gemini Flash)."""

import asyncio
import json
import logging
import re
import httpx
from narratio.db import get_connection

logger = logging.getLogger(__name__)

OPENROUTER_CHAT_URL = "https://openrouter.ai/api/v1/chat/completions"

SENTIMENT_PROMPT = """Classify this financial headline's sentiment as bearish, neutral, or bullish.
Return ONLY a JSON object: {"score": <float from -1.0 to 1.0>, "label": "<bearish|neutral|bullish>"}

Headline: {headline}
Summary: {summary}"""

MAX_RETRIES = 5
BACKOFF_BASE = 2  # seconds


async def _call_openrouter_chat_async(
    client: httpx.AsyncClient,
    messages: list[dict],
    api_key: str,
    model: str = "google/gemini-2.0-flash-001",
) -> dict:
    for attempt in range(MAX_RETRIES):
        resp = await client.post(
            OPENROUTER_CHAT_URL,
            json={"model": model, "messages": messages, "temperature": 0},
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            timeout=60,
        )
        if resp.status_code == 429:
            wait = min(BACKOFF_BASE ** (attempt + 1), 32)
            logger.warning("Sentiment API rate limited, retrying in %ds (attempt %d/%d)", wait, attempt + 1, MAX_RETRIES)
            await asyncio.sleep(wait)
            continue
        resp.raise_for_status()
        return resp.json()
    raise RuntimeError(f"OpenRouter API rate limited after {MAX_RETRIES} retries")


def _parse_sentiment_response(raw: str) -> tuple[float, str]:
    try:
        data = json.loads(raw.strip())
        return float(data["score"]), data["label"]
    except (json.JSONDecodeError, KeyError):
        raw_lower = raw.lower()
        if "bullish" in raw_lower:
            label = "bullish"
        elif "bearish" in raw_lower:
            label = "bearish"
        else:
            label = "neutral"

        numbers = re.findall(r"-?\d+\.?\d*", raw)
        score = float(numbers[0]) if numbers else (0.5 if label == "bullish" else -0.5 if label == "bearish" else 0.0)
        score = max(-1.0, min(1.0, score))
        return score, label


def _parse_batch_response(content: str, batch_len: int) -> list[dict]:
    try:
        sentiments = json.loads(content.strip().removeprefix("```json").removesuffix("```").strip())
        if isinstance(sentiments, dict):
            # LLM returned a single object instead of an array for a multi-item batch.
            # Use it as a low-confidence fallback rather than silently duplicating.
            score = sentiments.get("score", 0)
            label = sentiments.get("label", "neutral")
            if batch_len > 1:
                logger.warning(
                    "LLM returned single sentiment object for batch of %d; applying as low-confidence fallback",
                    batch_len,
                )
            sentiments = [{"index": j, "score": score, "label": label, "low_confidence": batch_len > 1} for j in range(batch_len)]
    except json.JSONDecodeError:
        score, label = _parse_sentiment_response(content)
        logger.warning("Failed to parse batch sentiment JSON; falling back to text parsing")
        sentiments = [{"index": j, "score": score, "label": label, "low_confidence": True} for j in range(batch_len)]
    return sentiments


async def _process_batch(
    client: httpx.AsyncClient,
    semaphore: asyncio.Semaphore,
    batch: list,
    api_key: str,
    model: str = "google/gemini-2.0-flash-001",
) -> list[tuple[int, float, str]]:
    headlines_text = "\n---\n".join(
        f"[{j}] Headline: {r['headline']}\nSummary: {r['summary']}"
        for j, r in enumerate(batch)
    )

    messages = [
        {
            "role": "user",
            "content": f"""Classify each headline's sentiment. Return a JSON array of objects, one per headline.
Each object: {{"index": <int>, "score": <float -1.0 to 1.0>, "label": "<bearish|neutral|bullish>"}}

{headlines_text}""",
        }
    ]

    async with semaphore:
        result = await _call_openrouter_chat_async(client, messages, api_key, model=model)

    content = result["choices"][0]["message"]["content"]
    sentiments = _parse_batch_response(content, len(batch))

    results = []
    for item in sentiments:
        idx = item.get("index", 0)
        if idx < len(batch):
            score = max(-1.0, min(1.0, float(item.get("score", 0))))
            label = item.get("label", "neutral")
            results.append((batch[idx]["id"], score, label))
    return results


async def _analyze_sentiment_async(
    db_path: str,
    api_key: str,
    batch_size: int = 20,
    max_concurrent: int = 10,
    model: str = "google/gemini-2.0-flash-001",
) -> int:
    conn = get_connection(db_path)

    rows = conn.execute(
        """SELECT a.id, a.headline, a.summary
           FROM articles a
           JOIN article_analysis aa ON aa.article_id = a.id
           WHERE aa.sentiment_score IS NULL
           ORDER BY a.id"""
    ).fetchall()

    if not rows:
        logger.info("No articles need sentiment analysis")
        conn.close()
        return 0

    logger.info("Analyzing sentiment for %d articles in %d batches", len(rows), (len(rows) + batch_size - 1) // batch_size)
    batches = [rows[i : i + batch_size] for i in range(0, len(rows), batch_size)]
    semaphore = asyncio.Semaphore(max_concurrent)

    async with httpx.AsyncClient() as client:
        tasks = [_process_batch(client, semaphore, batch, api_key, model=model) for batch in batches]
        batch_results = await asyncio.gather(*tasks, return_exceptions=True)

    total = 0
    failures = 0
    for result in batch_results:
        if isinstance(result, Exception):
            failures += 1
            logger.error("Sentiment batch failed: %s", result)
            continue
        for article_id, score, label in result:
            conn.execute(
                "UPDATE article_analysis SET sentiment_score = ?, sentiment_label = ? WHERE article_id = ?",
                (score, label, article_id),
            )
            total += 1
    conn.commit()
    conn.close()
    if failures:
        logger.warning("Sentiment complete: %d scored, %d batches failed", total, failures)
    else:
        logger.info("Sentiment complete: %d articles scored", total)
    return total


def analyze_sentiment(
    db_path: str,
    api_key: str,
    batch_size: int = 20,
    model: str = "google/gemini-2.0-flash-001",
) -> int:
    return asyncio.run(_analyze_sentiment_async(db_path, api_key, batch_size, model=model))
