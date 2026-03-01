# Phase 1 Revised — PRD Addendum

**Changes from original PRD:** Replace Finnhub with NYT API, replace Streamlit with Next.js + FastAPI.

---

## Change 1: NYT Developer API replaces Finnhub

### Why

Finnhub's free tier general news endpoint returns only ~100 recent articles with limited historical depth. The NYT Archive API returns **every article for a given month** in a single call, with history back to 1851. This gives us dense, high-quality data for narrative clustering.

### Data Source: NYT Archive API

**Endpoint:** `GET https://api.nytimes.com/svc/archive/v1/{year}/{month}.json?api-key={key}`

**What it returns:** All NYT articles for a given month in one response. Typical month = 3,000-5,000 articles. Response can be ~20MB for busy months.

**Fields per article:**

| Field | Maps to | Notes |
|-------|---------|-------|
| `headline.main` | `articles.headline` | Primary headline text |
| `abstract` | `articles.summary` | Article summary |
| `lead_paragraph` | (optional) | Opening paragraph — richer than abstract for embedding |
| `snippet` | (fallback) | Brief excerpt |
| `pub_date` | `articles.published_at` | ISO 8601 timestamp |
| `web_url` | `articles.url` | Link to full article |
| `source` | `articles.source` | Always "The New York Times" |
| `section_name` | `articles.category` | Section: Business, World, Technology, etc. |
| `news_desk` | (metadata) | Desk that produced the article |
| `keywords` | `articles.keywords` | Array of `{name, value}` objects — subjects, persons, organizations, glocations |
| `_id` | `articles.nyt_id` | Unique document ID (replaces `finnhub_id`) |
| `type_of_material` | (filter) | "News", "Op-Ed", "Letter", etc. — filter to News only |
| `document_type` | (filter) | "article", "multimedia" — filter to article only |
| `word_count` | (metadata) | Article length |

**Rate limits:**
- 500 requests/day, 5 requests/minute (per NYT developer docs)
- Archive API: 1 call = 1 full month of articles, so 12 calls = full year
- Article Search API: 10 req/min, 4,000 req/day (backup if needed)

**Filtering strategy:** Only ingest articles where:
- `document_type == "article"`
- `type_of_material == "News"` (exclude Op-Eds, Letters, Reviews)
- `section_name` in financial/macro-relevant sections: Business, World, U.S., Technology, Science, DealBook
- `word_count > 0` (skip empty stubs)

### Schema Changes

```sql
-- Rename finnhub_id to nyt_id
CREATE TABLE articles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nyt_id TEXT UNIQUE NOT NULL,       -- was: finnhub_id INTEGER
    headline TEXT NOT NULL,
    summary TEXT,                       -- abstract or lead_paragraph
    source TEXT,
    url TEXT,
    published_at TEXT NOT NULL,         -- was: INTEGER (unix timestamp) → now ISO 8601 string
    keywords TEXT,                      -- was: related_tickers → now JSON array of keyword objects
    category TEXT,                      -- section_name
    news_desk TEXT,                     -- new field
    word_count INTEGER,                -- new field
    ingested_at TEXT NOT NULL DEFAULT (datetime('now'))
);
```

**Key differences from Finnhub schema:**
- `nyt_id` is TEXT (not INTEGER) — NYT IDs are strings like `"nyt://article/..."`
- `published_at` stores ISO 8601 strings (not Unix timestamps) — simpler to work with
- `keywords` stores JSON array of keyword objects instead of ticker strings
- `related_tickers` column dropped (tickers not available from NYT)
- Added `news_desk` and `word_count` fields

### Ingestion Strategy

**Initial backfill:** Pull 12 months (2025-03 to 2026-02) via Archive API = 12 API calls. Expected: ~40,000-60,000 articles total, ~5,000-8,000 after section filtering.

**Ongoing:** Monthly Archive API call for the previous month. Supplement with Article Search API for the current partial month if freshness is needed.

**Pipeline changes:**
- Replace `finnhub-python` dependency with direct `httpx` calls to NYT API
- `ingest.py` rewritten: iterate months, call Archive API, filter, parse, store
- `parse_article()` maps NYT response fields to our schema
- Rate limit handling: 5 req/min max, add 12-second delay between calls
- Dedup on `nyt_id` (UNIQUE constraint)

### Embedding Input

For each article, embed: `"{headline}. {abstract or lead_paragraph}"` — same approach as before but with richer text from NYT abstracts.

### Environment Variables

```
NYT_API_KEY=your_nyt_api_key_here        # replaces FINNHUB_API_KEY
OPENROUTER_API_KEY=your_openrouter_api_key_here
```

---

## Change 2: Next.js + FastAPI replaces Streamlit

### Why

Streamlit is limiting for custom visualizations and professional-feeling dashboards. Next.js gives full control over layout, interactions, and custom D3/Plotly charts. FastAPI provides the JSON API contract between frontend and backend.

### Architecture

```
┌─────────────────────┐         ┌─────────────────────────┐
│   Next.js Frontend   │  JSON   │    FastAPI Backend       │
│   (React + Plotly)   │◄───────►│    (Python API)          │
│   Port 3000          │         │    Port 8000             │
└─────────────────────┘         └────────┬────────────────┘
                                         │
                                         ▼
                                ┌─────────────────┐
                                │  SQLite DB       │
                                │  data/narratio.db│
                                └─────────────────┘
```

### FastAPI Endpoints

| Endpoint | Method | Response | Notes |
|----------|--------|----------|-------|
| `GET /api/narratives` | GET | List of all narratives with latest metrics | Overview table data |
| `GET /api/narratives/{id}` | GET | Single narrative with weekly breakdown | Detail view data |
| `GET /api/narratives/{id}/headlines` | GET | Headlines for a narrative | Top headlines list |
| `GET /api/timeline` | GET | Timeline data for all narratives | Chart data |
| `POST /api/pipeline/run` | POST | Trigger pipeline execution | Pipeline trigger |
| `GET /api/pipeline/status` | GET | Pipeline run status | Progress feedback |

**Query parameters for `/api/timeline`:**
- `mode=attention|zscore` — which metric to return
- `start=YYYY-MM-DD&end=YYYY-MM-DD` — time range filter
- `narratives=1,2,3` — filter to specific narrative IDs

### Next.js Frontend

**Pages:**
- `/` — Dashboard: timeline chart + narrative overview table
- `/narratives/[id]` — Narrative detail: metrics, summary, sentiment chart, headlines

**Components:**
- `TimelineChart` — Plotly stacked area (attention) or multi-line (z-score)
- `NarrativeTable` — Sortable table of all narratives with key metrics
- `NarrativeDetail` — Metrics cards, summary, sentiment chart, headlines list
- `Sidebar` — Chart mode toggle, time range picker, narrative filter
- `PipelineButton` — Trigger pipeline run with loading state

**Tech:**
- Next.js 15 (App Router)
- TypeScript
- Tailwind CSS
- Plotly.js (via react-plotly.js) for charts
- Fetch API for backend calls (no extra client library needed)

### Project Structure

```
narrative_mvp/
  narratio/                # Python backend
    __init__.py
    config.py
    db.py
    data.py
    ingest.py             # REWRITTEN for NYT API
    embed.py
    cluster.py
    sentiment.py
    label.py
    summarize.py
    report.py
    pipeline.py
    api.py                # NEW: FastAPI app
  frontend/               # NEW: Next.js app
    package.json
    next.config.js
    tailwind.config.js
    app/
      layout.tsx
      page.tsx            # Dashboard
      narratives/
        [id]/
          page.tsx        # Detail view
    components/
      TimelineChart.tsx
      NarrativeTable.tsx
      NarrativeDetail.tsx
      Sidebar.tsx
  tests/
  data/
  pyproject.toml
```

### Dependencies

**Python (add to pyproject.toml):**
- `fastapi>=0.115`
- `uvicorn>=0.34`

**Remove:**
- `streamlit` (no longer needed)
- `finnhub-python` (replaced by direct httpx calls to NYT)

**Node.js (frontend/package.json):**
- `next`
- `react`, `react-dom`
- `typescript`
- `tailwindcss`
- `plotly.js`, `react-plotly.js`

### Development Workflow

```bash
# Terminal 1: Backend
uv run uvicorn narratio.api:app --reload --port 8000

# Terminal 2: Frontend
cd frontend && npm run dev

# Pipeline (unchanged)
uv run narratio
```

---

## Implementation Order

1. **Rewrite ingestion** — NYT Archive API replaces Finnhub. Update schema, config, ingest.py, tests.
2. **Add FastAPI** — Create api.py with all endpoints. Reuse data.py queries.
3. **Scaffold Next.js** — Create frontend/ with basic layout, routing, Tailwind.
4. **Dashboard page** — Timeline chart (Plotly), narrative table, sidebar controls.
5. **Detail page** — Narrative metrics, summary, sentiment chart, headlines.
6. **Pipeline integration** — POST /api/pipeline/run endpoint, progress feedback.
7. **Remove Streamlit** — Delete app.py, _run_app.py, remove streamlit dep.

---

## What Stays the Same

- Embedding (OpenRouter text-embedding-3-small)
- Clustering (HDBSCAN)
- Sentiment (OpenRouter Gemini Flash)
- Labeling (OpenRouter Gemini Flash)
- Summarization (OpenRouter Claude Sonnet)
- SQLite storage (with schema migration for NYT fields)
- Z-score and share-of-attention calculations
- `narratio` CLI entry point for pipeline
