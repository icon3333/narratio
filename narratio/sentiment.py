"""Sentiment analysis via OpenRouter (Gemini Flash)."""

import json
import re
import httpx
from narratio.db import get_connection

SENTIMENT_MODEL = "google/gemini-2.0-flash-001"
OPENROUTER_CHAT_URL = "https://openrouter.ai/api/v1/chat/completions"

SENTIMENT_PROMPT = """Classify this financial headline's sentiment as bearish, neutral, or bullish.
Return ONLY a JSON object: {"score": <float from -1.0 to 1.0>, "label": "<bearish|neutral|bullish>"}

Headline: {headline}
Summary: {summary}"""


def _call_openrouter_chat(messages: list[dict], api_key: str, model: str = SENTIMENT_MODEL) -> dict:
    resp = httpx.post(
        OPENROUTER_CHAT_URL,
        json={"model": model, "messages": messages, "temperature": 0},
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()


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


def analyze_sentiment(
    db_path: str,
    api_key: str,
    batch_size: int = 20,
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
        conn.close()
        return 0

    total = 0
    for i in range(0, len(rows), batch_size):
        batch = rows[i : i + batch_size]

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

        result = _call_openrouter_chat(messages, api_key)
        content = result["choices"][0]["message"]["content"]

        try:
            sentiments = json.loads(content.strip().removeprefix("```json").removesuffix("```").strip())
            if isinstance(sentiments, dict):
                # Single dict response: apply to all items in the batch
                sentiments = [{"index": j, "score": sentiments.get("score", 0), "label": sentiments.get("label", "neutral")} for j in range(len(batch))]
        except json.JSONDecodeError:
            score, label = _parse_sentiment_response(content)
            sentiments = [{"index": j, "score": score, "label": label} for j in range(len(batch))]

        for item in sentiments:
            idx = item.get("index", 0)
            if idx < len(batch):
                score = max(-1.0, min(1.0, float(item.get("score", 0))))
                label = item.get("label", "neutral")
                conn.execute(
                    "UPDATE article_analysis SET sentiment_score = ?, sentiment_label = ? WHERE article_id = ?",
                    (score, label, batch[idx]["id"]),
                )
                total += 1

        conn.commit()

    conn.close()
    return total
