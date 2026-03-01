# Phase 0 Design: Pipeline Proof

**Date:** 2026-03-01
**Goal:** Ingest ~3 months of Finnhub general news, cluster into narratives, and verify they make sense via CLI report.

## Architecture

Single Python package (`narratio/`). All ML/LLM work via OpenRouter APIs. SQLite for structured storage, numpy for embedding vectors. CLI report for output.

## Pipeline Stages

1. **Ingest** — Finnhub general news API (`/api/v1/news?category=general`), paginate back ~3 months via `minId`, store in SQLite `articles` table (immutable).
2. **Embed** — OpenRouter `openai/text-embedding-3-small` (1536-dim), batch 100 articles/request, save embeddings to numpy array + reference in SQLite `article_analysis`.
3. **Cluster** — HDBSCAN (`min_cluster_size=15`, cosine metric) on full 3-month embedding set. Assign cluster IDs to `article_analysis`.
4. **Sentiment** — OpenRouter Gemini Flash, classify each article as bearish/neutral/bullish with numeric score [-1, +1]. Store in `article_analysis`.
5. **Label** — OpenRouter Gemini Flash, top-10 headlines per cluster -> 3-6 word narrative label. Create `narratives` records.
6. **Summarize** — OpenRouter quality model (Claude Sonnet), generate weekly story evolution summaries per narrative. Store in `narrative_weeks`.
7. **Match** — Cosine similarity (>=0.75) on cluster centroids to track narrative continuity across weekly windows.
8. **Report** — CLI output (via `rich`) showing all discovered narratives: label, article count, share of attention, sentiment, top 5 headlines, story summary.

## Storage

- SQLite database: `data/narratio.db`
- Numpy embeddings: `data/embeddings.npy`
- Both gitignored

## SQLite Schema (Simplified)

- **articles** — `id`, `finnhub_id`, `headline`, `summary`, `source`, `url`, `published_at`, `related_tickers`, `category`, `ingested_at`
- **article_analysis** — `article_id`, `embedding_index` (ref into numpy array), `sentiment_score`, `sentiment_label`, `cluster_id`, `narrative_id`
- **narratives** — `id`, `label`, `first_seen`, `last_seen`, `status`, `centroid_embedding_index`
- **narrative_weeks** — `narrative_id`, `week_start`, `article_count`, `share_of_attention`, `z_score`, `sentiment_mean`, `summary`, `top_headline_ids`
- **weekly_totals** — `week_start`, `total_articles`, `total_clustered`, `total_noise`

## Dependencies

- `finnhub-python` — Finnhub API client
- `httpx` — OpenRouter API calls
- `hdbscan` — Density-based clustering
- `numpy` — Embedding storage and math
- `scikit-learn` — Cosine similarity, utilities
- `python-dotenv` — Environment variable management
- `rich` — CLI formatting and tables

## Environment Variables

- `FINNHUB_API_KEY` — Finnhub free tier API key
- `OPENROUTER_API_KEY` — OpenRouter API key

## Project Structure

```
narratio/
  pyproject.toml
  .env.example
  narratio/
    __init__.py
    pipeline.py       # Main orchestrator
    ingest.py          # Finnhub -> SQLite
    embed.py           # OpenRouter embeddings -> numpy
    cluster.py         # HDBSCAN clustering
    sentiment.py       # OpenRouter sentiment
    label.py           # OpenRouter labeling (Gemini Flash)
    summarize.py       # OpenRouter summarization (Claude Sonnet)
    match.py           # Cosine similarity matching
    report.py          # CLI report output
    db.py              # SQLite helpers
    config.py          # Settings from env vars
  data/                # SQLite + numpy (gitignored)
  tests/
```

## Success Criteria

- Discovers 10-30 distinct, coherent narratives from 3 months of news
- Narratives are human-recognizable (e.g., "Fed Rate Expectations", "AI Capex Boom")
- Share of attention and z-scores produce meaningful differentiation
- Pipeline runs end-to-end without manual intervention
