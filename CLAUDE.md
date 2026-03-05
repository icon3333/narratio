# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Narratio (Narrative Radar)** — A financial market narrative tracking tool that automatically discovers, tracks, and visualizes macro market narratives from financial news.

## Development Commands

```bash
uv run narratio                                    # run full pipeline (current month)
python narratio/backfill.py --start 2025-01        # backfill historical data
uv run uvicorn narratio.api:app --reload           # API server (port 8000)
cd frontend && npm run dev                         # frontend dev server (port 3000)
uv run pytest                                      # all tests
uv run pytest tests/test_cluster.py                # single test file
uv run pytest tests/test_cluster.py -k test_name   # single test
```

## Architecture

### Tech Stack

- **Backend:** Python (≥3.12) + FastAPI, managed with `uv`
- **Frontend:** Next.js 16 + React 19 + TypeScript, Plotly.js for charts, Tailwind 4
- **Database:** SQLite with WAL mode; embeddings stored in `data/embeddings.npy`
- **ML:** UMAP (dimensionality reduction) + HDBSCAN (clustering), all via scikit-learn ecosystem
- **Embeddings:** OpenRouter API (`openai/text-embedding-3-small`) — no local models
- **LLM:** OpenRouter as single gateway — Gemini Flash for labeling/sentiment, Claude Sonnet for summarization
- **Data Sources:** NYT Archive API + Guardian Open Platform
- **Entry point:** `narratio` CLI → `narratio.pipeline:main` (defined in `pyproject.toml`)

### Analysis Pipeline (9 steps)

```
Embed (OpenRouter) → Filter Relevance → Cluster (UMAP+HDBSCAN) → Merge Clusters
  → Sentiment (Gemini Flash) → Label Narratives (Gemini Flash) → Weekly Analytics
  → Significance Scores → Summarize (Claude Sonnet)
```

Ingestion is separate: `run_pipeline()` ingests then runs analysis; `run_analysis()` runs analysis only. Every run recalculates `share_of_attention` and `z_score` across the entire timeline. The analysis layer is fully regenerable from the immutable `articles` table.

### Data Model (SQLite)

- **`articles`** — Immutable source of truth. Never modified after ingestion.
- **`article_analysis`** — Computed: embedding index, sentiment, cluster assignment, narrative assignment per article.
- **`narratives`** — Long-lived entities with label, centroid embedding index, status (active/dormant), significance score.
- **`narrative_weeks`** — Computed weekly analytics: attention share, z-score, sentiment mean, LLM summaries.
- **`weekly_totals`** — Denominators for share-of-attention calculations.

### API Endpoints

```
GET  /api/narratives                        — list all narratives
GET  /api/narratives/{id}                   — narrative detail
GET  /api/narratives/{id}/headlines          — top headlines for a narrative
GET  /api/articles                          — paginated articles (query: page, per_page, source, search)
GET  /api/stats                             — database-level stats
GET  /api/arising                           — emerging narratives
GET  /api/timeline                          — timeline data (query: mode, top_n, start, end, narratives)
POST /api/pipeline/run                      — trigger full pipeline as background task
POST /api/pipeline/analyze                  — trigger analysis-only as background task
GET  /api/pipeline/status                   — pipeline running status + step progress
```

### Backend Modules (`narratio/`)

| Module | Purpose |
|--------|---------|
| `pipeline.py` | Main orchestrator: `run_pipeline()` and `run_analysis()` |
| `api.py` | FastAPI backend |
| `db.py` | SQLite schema, init, migrations, connection helpers |
| `ingest.py` | NYT Archive API ingestion |
| `ingest_guardian.py` | Guardian Open Platform ingestion |
| `embed.py` | Async batch embedding via OpenRouter |
| `cluster.py` | UMAP + HDBSCAN clustering, cluster merging, relevance filtering |
| `sentiment.py` | Async batch sentiment scoring via OpenRouter |
| `label.py` | Narrative labeling and matching via OpenRouter |
| `summarize.py` | Weekly analytics computation and LLM summarization |
| `data.py` | Query/analytics helpers consumed by the API |
| `config.py` | Dataclass config from env vars |
| `report.py` | Rich console report generation |
| `backfill.py` | Historical ingestion CLI (`--start YYYY-MM --end YYYY-MM`) |

### Other Directories

- **`frontend/`** — Next.js dashboard with narrative table, timeline chart, arising tab, articles browser.

## Key Design Decisions

- **Weekly granularity** — intentional, not a limitation. Reduces noise, matches purpose.
- **Unsupervised discovery** — narratives emerge from HDBSCAN clustering, not predefined categories.
- **Two-tier LLM via OpenRouter** — cheap model for labeling/sentiment, quality model for summarization. Model swaps are config changes.
- **Headline-level only** — headlines + snippets, not full articles. Faster and cheaper.
- **Full-history recalibration** — z-scores and shares recomputed over entire history each run for consistency.
- **Cosine similarity matching (≥0.80)** — for narrative continuity between weeks. Tunable threshold.

## Development Phases

| Phase | Focus |
|-------|-------|
| **0 (Proof)** | Ingest 3 months, embed + cluster, manually verify narratives make sense |
| **1 (MVP)** | Full pipeline, Streamlit dashboard, weekly cron |
| **2 (Polish)** | Comparison view, alerts, mutation tracking |
| **3 (Scale)** | S&P 500, JSON API, React/Next.js frontend |

<!-- gitnexus:start -->
# GitNexus MCP

This project is indexed by GitNexus as **narratio** (243 symbols, 638 relationships, 20 execution flows).

## Always Start Here

1. **Read `gitnexus://repo/{name}/context`** — codebase overview + check index freshness
2. **Match your task to a skill below** and **read that skill file**
3. **Follow the skill's workflow and checklist**

> If step 1 warns the index is stale, run `npx gitnexus analyze` in the terminal first.

## Skills

| Task | Read this skill file |
|------|---------------------|
| Understand architecture / "How does X work?" | `.claude/skills/gitnexus/gitnexus-exploring/SKILL.md` |
| Blast radius / "What breaks if I change X?" | `.claude/skills/gitnexus/gitnexus-impact-analysis/SKILL.md` |
| Trace bugs / "Why is X failing?" | `.claude/skills/gitnexus/gitnexus-debugging/SKILL.md` |
| Rename / extract / split / refactor | `.claude/skills/gitnexus/gitnexus-refactoring/SKILL.md` |
| Tools, resources, schema reference | `.claude/skills/gitnexus/gitnexus-guide/SKILL.md` |
| Index, status, clean, wiki CLI commands | `.claude/skills/gitnexus/gitnexus-cli/SKILL.md` |

<!-- gitnexus:end -->
