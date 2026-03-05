"""Embed article headlines via OpenRouter embeddings API."""

import asyncio
import logging
from itertools import batched
import numpy as np
import httpx
from pathlib import Path
from narratio.db import get_connection
from narratio.openrouter import call_embed_async

logger = logging.getLogger(__name__)


async def _process_batch(
    client: httpx.AsyncClient,
    semaphore: asyncio.Semaphore,
    batch: list,
    api_key: str,
    model: str = "openai/text-embedding-3-small",
) -> list[tuple[int, list[float]]]:
    """Process one embedding batch. Returns list of (article_id, embedding)."""
    texts = [f"{r['headline']}. {r['summary']}" for r in batch]

    async with semaphore:
        result = await call_embed_async(client, texts, api_key, model)

    sorted_data = sorted(result["data"], key=lambda x: x["index"])

    results = []
    for j, item in enumerate(sorted_data):
        results.append((batch[j]["id"], item["embedding"]))
    return results


async def _embed_articles_async(
    db_path: str,
    embeddings_path: str,
    api_key: str,
    batch_size: int = 100,
    max_concurrent: int = 10,
    model: str = "openai/text-embedding-3-small",
) -> int:
    conn = get_connection(db_path)
    try:
        rows = conn.execute(
            """SELECT a.id, a.headline, a.summary
               FROM articles a
               JOIN article_analysis aa ON aa.article_id = a.id
               WHERE aa.embedding_index IS NULL
               ORDER BY a.id"""
        ).fetchall()

        if not rows:
            logger.info("No articles to embed")
            return 0

        logger.info("Embedding %d articles in %d batches", len(rows), (len(rows) + batch_size - 1) // batch_size)
        emb_path = Path(embeddings_path)
        if emb_path.exists():
            existing = np.load(str(emb_path))
            all_embeddings = list(existing)
        else:
            emb_path.parent.mkdir(parents=True, exist_ok=True)
            all_embeddings = []

        batches = list(batched(rows, batch_size))

        semaphore = asyncio.Semaphore(max_concurrent)

        async with httpx.AsyncClient() as client:
            tasks = [
                _process_batch(client, semaphore, batch, api_key, model)
                for batch in batches
            ]
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)

        # Assign indices sequentially after all batches complete.
        total = 0
        failures = 0
        updates = []
        for result in batch_results:
            if isinstance(result, Exception):
                failures += 1
                logger.error("Embedding batch failed: %s", result)
                continue
            for article_id, embedding in result:
                emb_index = len(all_embeddings)
                all_embeddings.append(embedding)
                updates.append((emb_index, article_id))
                total += 1

        conn.executemany(
            "UPDATE article_analysis SET embedding_index = ? WHERE article_id = ?",
            updates,
        )
        conn.commit()
        np.save(str(emb_path), np.array(all_embeddings, dtype=np.float32))
        if failures:
            logger.warning("Embedding complete: %d succeeded, %d batches failed", total, failures)
        else:
            logger.info("Embedding complete: %d articles embedded", total)
        return total
    finally:
        conn.close()


def embed_articles(
    db_path: str,
    embeddings_path: str,
    api_key: str,
    batch_size: int = 100,
    model: str = "openai/text-embedding-3-small",
) -> int:
    return asyncio.run(_embed_articles_async(db_path, embeddings_path, api_key, batch_size, model=model))
