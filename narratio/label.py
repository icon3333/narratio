"""Narrative labeling via OpenRouter (Gemini Flash)."""

import numpy as np
import httpx
from datetime import datetime
from narratio.db import get_connection

LABEL_MODEL = "google/gemini-2.0-flash-001"
OPENROUTER_CHAT_URL = "https://openrouter.ai/api/v1/chat/completions"


def _call_openrouter_chat(messages: list[dict], api_key: str, model: str = LABEL_MODEL) -> dict:
    """Send a chat completion request to OpenRouter."""
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


def _build_label_prompt(headlines: list[str]) -> str:
    """Build a prompt asking the LLM to generate a short narrative label."""
    headlines_text = "\n".join(f"- {h}" for h in headlines[:10])
    return f"""These headlines belong to the same financial news cluster. Generate a short, descriptive label (3-6 words) that captures the common theme.

Headlines:
{headlines_text}

Return ONLY the label, nothing else. Example: "Fed Rate Cut Expectations" or "China Property Crisis"."""


def label_clusters(
    db_path: str,
    embeddings_path: str,
    api_key: str,
) -> int:
    """Label each cluster by asking an LLM to name it, then create narrative rows.

    Returns the number of narratives created.
    """
    conn = get_connection(db_path)
    embeddings = np.load(embeddings_path)

    clusters = conn.execute(
        "SELECT DISTINCT cluster_id FROM article_analysis WHERE cluster_id IS NOT NULL ORDER BY cluster_id"
    ).fetchall()

    n_labeled = 0

    for row in clusters:
        cluster_id = row["cluster_id"]

        articles = conn.execute(
            """SELECT a.id, a.headline, a.published_at, aa.embedding_index
               FROM articles a
               JOIN article_analysis aa ON aa.article_id = a.id
               WHERE aa.cluster_id = ?
               ORDER BY a.published_at DESC
               LIMIT 10""",
            (cluster_id,),
        ).fetchall()

        if not articles:
            continue

        headlines = [a["headline"] for a in articles]
        messages = [{"role": "user", "content": _build_label_prompt(headlines)}]
        result = _call_openrouter_chat(messages, api_key)
        label = result["choices"][0]["message"]["content"].strip().strip('"').strip("'")

        # Get all embedding indices for this cluster to compute centroid
        all_cluster_articles = conn.execute(
            "SELECT embedding_index FROM article_analysis WHERE cluster_id = ? AND embedding_index IS NOT NULL",
            (cluster_id,),
        ).fetchall()
        all_indices = [r["embedding_index"] for r in all_cluster_articles]
        centroid_index = all_indices[0]  # placeholder

        dates = conn.execute(
            """SELECT MIN(a.published_at) as first, MAX(a.published_at) as last
               FROM articles a JOIN article_analysis aa ON aa.article_id = a.id
               WHERE aa.cluster_id = ?""",
            (cluster_id,),
        ).fetchone()

        first_seen = datetime.fromisoformat(dates["first"].replace("+0000", "+00:00")).strftime("%Y-%m-%d")
        last_seen = datetime.fromisoformat(dates["last"].replace("+0000", "+00:00")).strftime("%Y-%m-%d")

        cursor = conn.execute(
            """INSERT INTO narratives (label, first_seen, last_seen, status, centroid_embedding_index)
               VALUES (?, ?, ?, 'active', ?)""",
            (label, first_seen, last_seen, centroid_index),
        )
        narrative_id = cursor.lastrowid

        conn.execute(
            "UPDATE article_analysis SET narrative_id = ? WHERE cluster_id = ?",
            (narrative_id, cluster_id),
        )

        conn.commit()
        n_labeled += 1

    conn.close()
    return n_labeled
