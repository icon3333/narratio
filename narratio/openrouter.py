"""Shared OpenRouter API helpers with retry + backoff."""

import asyncio
import logging
import time
import httpx

logger = logging.getLogger(__name__)

OPENROUTER_CHAT_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_EMBED_URL = "https://openrouter.ai/api/v1/embeddings"

MAX_RETRIES = 5
BACKOFF_BASE = 2  # seconds


def _headers(api_key: str) -> dict:
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }


def _backoff(attempt: int) -> float:
    return min(BACKOFF_BASE ** (attempt + 1), 32)


async def call_chat_async(
    client: httpx.AsyncClient,
    messages: list[dict],
    api_key: str,
    model: str,
    temperature: float = 0,
    timeout: float = 60,
) -> dict:
    """Async chat completion with retry on 429."""
    for attempt in range(MAX_RETRIES):
        resp = await client.post(
            OPENROUTER_CHAT_URL,
            json={"model": model, "messages": messages, "temperature": temperature},
            headers=_headers(api_key),
            timeout=timeout,
        )
        if resp.status_code == 429:
            wait = _backoff(attempt)
            logger.warning("Chat API rate limited, retrying in %ds (attempt %d/%d)", wait, attempt + 1, MAX_RETRIES)
            await asyncio.sleep(wait)
            continue
        resp.raise_for_status()
        return resp.json()
    raise RuntimeError(f"OpenRouter API rate limited after {MAX_RETRIES} retries")


def call_chat_sync(
    messages: list[dict],
    api_key: str,
    model: str,
    temperature: float = 0,
    timeout: float = 120,
) -> dict:
    """Sync chat completion with retry on 429 and ReadTimeout."""
    for attempt in range(MAX_RETRIES):
        try:
            resp = httpx.post(
                OPENROUTER_CHAT_URL,
                json={"model": model, "messages": messages, "temperature": temperature},
                headers=_headers(api_key),
                timeout=timeout,
            )
            if resp.status_code == 429:
                wait = _backoff(attempt)
                logger.warning("Chat API rate limited, retrying in %ds (attempt %d/%d)", wait, attempt + 1, MAX_RETRIES)
                time.sleep(wait)
                continue
            resp.raise_for_status()
            return resp.json()
        except httpx.ReadTimeout:
            wait = _backoff(attempt)
            logger.warning("Chat API read timeout, retrying in %ds (attempt %d/%d)", wait, attempt + 1, MAX_RETRIES)
            time.sleep(wait)
    raise RuntimeError(f"OpenRouter API failed after {MAX_RETRIES} retries")


async def call_embed_async(
    client: httpx.AsyncClient,
    texts: list[str],
    api_key: str,
    model: str = "openai/text-embedding-3-small",
    timeout: float = 60,
) -> dict:
    """Async embedding with retry on 429."""
    payload = {"model": model, "input": texts}
    for attempt in range(MAX_RETRIES):
        resp = await client.post(
            OPENROUTER_EMBED_URL,
            json=payload,
            headers=_headers(api_key),
            timeout=timeout,
        )
        if resp.status_code == 429:
            wait = _backoff(attempt)
            logger.warning("Embedding API rate limited, retrying in %ds (attempt %d/%d)", wait, attempt + 1, MAX_RETRIES)
            await asyncio.sleep(wait)
            continue
        resp.raise_for_status()
        return resp.json()
    raise RuntimeError(f"Embedding API rate limited after {MAX_RETRIES} retries")
