# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Narratio (Narrative Radar)** — A financial market narrative tracking tool that automatically discovers, tracks, and visualizes macro market narratives from financial news. Currently in pre-development (PRD complete, no code yet). See `narrative_prd.md` for full requirements.

## Architecture

### Tech Stack

- **Backend:** Python + FastAPI (JSON API + ML pipeline)
- **Frontend:** Next.js (React) + TypeScript, D3.js/Recharts for custom visualizations
- **Database:** PostgreSQL + pgvector
- **ML:** sentence-transformers (embeddings), HDBSCAN (clustering), FinBERT (sentiment)
- **LLM:** OpenRouter as single gateway — Gemini Flash for cheap labeling, Claude Sonnet/Gemini Pro for quality summarization
- **Data Source:** Finnhub general news API (single source, free tier)
- **Scheduler:** cron or GitHub Actions for weekly batch runs

### Data Pipeline (Weekly Batch)

```
Ingest (Finnhub) → Embed (sentence-transformers) → Cluster (HDBSCAN) → Sentiment (FinBERT)
  → Label (OpenRouter/Flash) → Summarize (OpenRouter/Sonnet) → Match (cosine sim ≥0.75) → Store (PostgreSQL)
```

Every pipeline run recalculates `share_of_attention` and `z_score` across the **entire timeline** at all granularities (weekly, monthly, quarterly). The analysis layer is fully regenerable from the immutable `articles` table.

### Data Model

- **`articles`** — Immutable source of truth. Never modified after ingestion.
- **`article_analysis`** — Computed: embeddings, sentiment, narrative assignment per article.
- **`narratives`** — Long-lived entities with label, centroid embedding, status (active/dormant).
- **`narrative_weeks/months/quarters`** — Computed analytics: attention share, z-score, sentiment, LLM summaries.
- **`weekly/monthly/quarterly_totals`** — Denominators for share-of-attention calculations.
- **`narrative_tickers`** — Ticker-narrative linkage from Finnhub's "related" field.
- **`narrative_mutations`** — Tracks narrative evolution/splits.

### API Endpoints

Backend exposes JSON endpoints consumed by the frontend:
- `/api/narratives` — List all narratives
- `/api/narratives/{id}/weeks` — Weekly data for a narrative
- `/api/timeline?granularity=weekly|monthly|quarterly` — Timeline data
- `/api/alerts` — Emergence and shift alerts

## Key Design Decisions

- **Weekly granularity** — intentional, not a limitation. Reduces noise, matches purpose.
- **Unsupervised discovery** — narratives emerge from HDBSCAN clustering, not predefined categories.
- **Two-tier LLM via OpenRouter** — cheap model for labeling, quality model for summarization. Model swaps are config changes.
- **Headline-level only** — headlines + snippets, not full articles. Faster and cheaper.
- **Full-history recalibration** — z-scores and shares recomputed over entire history each run for consistency.
- **Cosine similarity matching (≥0.75)** — for narrative continuity between weeks. Tunable threshold.

## Development Phases

| Phase | Focus |
|-------|-------|
| **0 (Proof)** | Ingest 3 months, embed + cluster, manually verify narratives make sense |
| **1 (MVP)** | Full pipeline, Streamlit dashboard, weekly cron |
| **2 (Polish)** | Comparison view, alerts, mutation tracking |
| **3 (Scale)** | S&P 500, JSON API, React/Next.js frontend |
