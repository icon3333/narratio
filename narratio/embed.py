"""Embed article headlines via OpenRouter embeddings API."""

import numpy as np
import httpx
from pathlib import Path
from narratio.db import get_connection

EMBED_MODEL = "openai/text-embedding-3-small"
OPENROUTER_EMBED_URL = "https://openrouter.ai/api/v1/embeddings"


def _build_embed_request(texts: list[str]) -> dict:
    return {
        "model": EMBED_MODEL,
        "input": texts,
    }


def _call_openrouter_embed(texts: list[str], api_key: str) -> dict:
    req = _build_embed_request(texts)
    resp = httpx.post(
        OPENROUTER_EMBED_URL,
        json=req,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()


def embed_articles(
    db_path: str,
    embeddings_path: str,
    api_key: str,
    batch_size: int = 100,
) -> int:
    conn = get_connection(db_path)

    rows = conn.execute(
        """SELECT a.id, a.headline, a.summary
           FROM articles a
           JOIN article_analysis aa ON aa.article_id = a.id
           WHERE aa.embedding_index IS NULL
           ORDER BY a.id"""
    ).fetchall()

    if not rows:
        conn.close()
        return 0

    emb_path = Path(embeddings_path)
    if emb_path.exists():
        existing = np.load(str(emb_path))
        all_embeddings = list(existing)
    else:
        emb_path.parent.mkdir(parents=True, exist_ok=True)
        all_embeddings = []

    total = 0
    for i in range(0, len(rows), batch_size):
        batch = rows[i : i + batch_size]
        texts = [f"{r['headline']}. {r['summary']}" for r in batch]

        result = _call_openrouter_embed(texts, api_key)

        sorted_data = sorted(result["data"], key=lambda x: x["index"])

        for j, item in enumerate(sorted_data):
            emb_index = len(all_embeddings)
            all_embeddings.append(item["embedding"])
            article_id = batch[j]["id"]
            conn.execute(
                "UPDATE article_analysis SET embedding_index = ? WHERE article_id = ?",
                (emb_index, article_id),
            )
            total += 1

        conn.commit()

    np.save(str(emb_path), np.array(all_embeddings, dtype=np.float32))
    conn.close()
    return total
