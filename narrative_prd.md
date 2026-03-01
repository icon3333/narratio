#  Narratio— Product Requirements Document

**Track the Stories Markets Tell Themselves**

Version 1.0 | February 2026 | Draft

*A tool for observing how market narratives emerge, evolve, and fade over weeks and months.*

---

## 1. Problem Statement

Markets move on narratives before they move on data. Macro stories like "Fed pivot," "AI bubble," "soft landing," or "trade war escalation" drive capital allocation, risk appetite, and sector rotation for weeks or months at a time. Yet most financial news tools are optimized for the daily firehose: real-time feeds, daily sentiment scores, headline tickers.

There is no accessible, free tool that answers the question: **What macro stories is the market telling itself right now, how have those stories evolved, and which ones are emerging or dying?**

> **Core insight:** Narrative arcs — emergence → consensus → exhaustion — are leading indicators. By the time a narrative reaches peak frequency, the trade is often crowded.

---

## 2. Vision & Core Concepts

Narrative Radar is a tool that ingests financial news, automatically discovers recurring macro themes ("narratives"), and tracks their lifecycle over weeks and months. It surfaces four dimensions per narrative:

| Dimension | Definition | Example |
|---|---|---|
| **Share of Attention** | What percentage of total macro coverage this narrative represents in a given week. Attention is zero-sum: if one narrative surges, others get crowded out. | "Tariff escalation" went from 5% to 35% of coverage in 6 weeks, crowding out "soft landing" coverage. |
| **Z-Score (Anomaly)** | How unusual this week's coverage is relative to the narrative's own rolling baseline. Calculated as `(current_week – rolling_mean) / rolling_std` over a trailing 8-week window. | "Inflation" averaged 10% of coverage for months. A jump to 25% produces a z-score of +2.5 — a clear anomaly even if it's not the #1 topic. |
| **Story** | What the narrative is about and how its framing mutates over time. | "Rate hikes" → "Rate pause" → "Rate cuts" represents a single evolving narrative thread. |
| **Mood** | Aggregate sentiment of articles within the narrative (bearish / neutral / bullish). | "AI capex boom" narrative mood shifted from euphoric (+0.7) to anxious (-0.2) over 3 months. |

### 2.1 Key Definitions

- **Narrative:** A recurring theme or storyline in financial news that persists across multiple articles over at least 2 weeks. Examples: "de-dollarization," "Mag7 concentration risk," "commercial real estate stress."
- **Narrative Arc:** The lifecycle of a narrative: Emergence → Growth → Peak → Decline → Dormancy (or Mutation into a new narrative).
- **Narrative Cluster:** A group of semantically similar headlines/articles that collectively form a narrative. Detected via embedding similarity.
- **Narrative Mutation:** When a narrative's framing shifts substantially (e.g., "inflation surge" → "disinflation hope") while remaining thematically linked.

---

## 3. Target Users

| Persona | Goal | Key Feature |
|---|---|---|
| **Macro Investor** | Identify when consensus narratives are overextended or a new theme is forming | Narrative Arc Timeline, Emergence Alerts |
| **Quant Researcher** | Build narrative-based sentiment factors for systematic strategies | API access, raw data export, narrative scoring |
| **Portfolio Manager** | Monitor narrative risk — is the market pricing in a story that might reverse? | Narrative Comparison, Mood Shift Alerts |
| **Financial Journalist** | Identify underreported emerging themes before they become mainstream | Narrative Discovery, Emergence Detection |

---

## 4. Feature Requirements

### 4.1 Narrative Discovery Engine (P0 — Must Have)

Automatically detect and label narratives from raw news. No manual tagging required.

**How it works:**

- **Embed:** Convert each headline + snippet into a vector using a sentence-transformer model (e.g., all-MiniLM-L6-v2 for speed, or FinBERT-based for financial domain accuracy).
- **Cluster:** Group similar embeddings using HDBSCAN (density-based, handles noise, no need to pre-specify k). Run weekly on the trailing 4-week window.
- **Label (cheap LLM):** Use a fast, inexpensive model via OpenRouter (e.g., Gemini Flash) to generate a short, human-readable label for each cluster from its top-10 representative headlines. E.g., "Fed Rate Cut Expectations" or "China Property Crisis."
- **Summarize (quality LLM):** Use a more capable model via OpenRouter (e.g., Claude Sonnet, Gemini Pro) to generate weekly story evolution summaries. This task requires comparing the current week's framing against prior summaries to describe how the narrative shifted.
- **Track:** Match new weekly clusters to existing narratives using centroid cosine similarity (threshold ≥0.75). If no match, flag as "emerging narrative."

### 4.2 Narrative Timeline Dashboard (P0)

The primary view. Three controls shape what the user sees:

1. **Chart mode toggle:** Share of Attention (default) vs. Z-Score Anomaly
2. **Timeline granularity dropdown:** Weekly / Monthly / Yearly
3. **Time range selector:** How far back to look

#### Timeline Granularity

| Granularity | X-axis unit | Best for | Data shown |
|---|---|---|---|
| **Weekly** (default) | 1 week | Tactical — what shifted this week? Spotting emerging narratives early. | Each data point = 1 week of articles. Default range: 12 weeks. Max: 52 weeks. |
| **Monthly** | 1 calendar month | Strategic — how are themes evolving quarter over quarter? Smooths out weekly noise. | Each data point = 1 month of articles (aggregated from weekly data). Default range: 6 months. Max: 12 months. |
| **Yearly** | 1 quarter (displayed as Q1/Q2/Q3/Q4) | Big picture — what defined each era? Narrative regime changes. | Each data point = 1 quarter. Requires 1+ year of accumulated data to be useful. Default/max: full history. |

**Aggregation rules when switching granularity:**

- **Share of attention:** Recalculated at the selected granularity. Monthly share = narrative's article count for that month / total articles that month. Not an average of weekly shares (avoids distortion from variable weekly volumes).
- **Z-score:** Baseline window scales with granularity. Weekly: trailing 8 weeks. Monthly: trailing 6 months. Yearly: trailing 4 quarters.
- **Mood:** Weighted average of article-level sentiment within the period, weighted by article count per week (so high-volume weeks contribute more).
- **Story summary:** Weekly view shows per-week summaries. Monthly view shows a single LLM-generated summary per month (synthesized from weekly summaries). Yearly view shows one summary per quarter.
- **Top headlines:** Weekly shows top 5 per week. Monthly shows top 10 per month. Yearly shows top 5 per quarter.

#### Default View: Share of Attention (100% Stacked)

A horizontal timeline (x-axis = weeks) showing all narratives as a 100% stacked area chart. Each narrative's height represents its percentage of total macro news coverage that week. This directly answers: "What is the market focused on, and what got crowded out?"

- **Time range:** Default 12 weeks, expandable to 52 weeks (full year from Finnhub free tier).
- **Y-axis:** 0–100% of total weekly article volume. Narratives stacked, ranked by current-week share.
- **Color encoding:** Each narrative gets a persistent color. Mood is shown via color intensity or border glow, not the stream color itself (avoids confusion between narrative identity and sentiment).
- **Interaction:** Click a narrative stream to drill into representative headlines, mood trend, and story evolution.
- **Annotations:** Auto-mark key events (FOMC dates, earnings seasons, geopolitical events) as vertical reference lines.

#### Toggle View: Z-Score Anomaly Detection

Switches to a multi-line chart where each narrative is plotted as its z-score: `(current_week_share – rolling_8w_mean) / rolling_8w_std`. This answers: "What just changed dramatically relative to its own baseline?" A narrative at z = +2.0 is receiving 2 standard deviations more attention than its recent average — regardless of whether it's the #1 or #5 topic.

- **Baseline window:** Trailing 8 weeks (tunable). Recalculates every week against the full available history.
- **Alert thresholds:** Visual bands at z = ±1.5 and ±2.0. Narratives crossing ±2.0 are highlighted.
- **Key insight:** This is how the inflation example works. If inflation coverage normally sits at ~10% and jumps to 25%, the z-score spikes to +2.5, making it visually obvious even though AI coverage at 30% is still higher in absolute terms.

### 4.3 Narrative Detail View (P0)

For each narrative, show a detail panel. All charts and data adapt to the currently selected timeline granularity:

- **Attention chart:** Share of attention (%) per period over time, with the narrative's z-score overlaid as a secondary axis.
- **Mood chart:** Sentiment score per period over time (line chart with green/red area fill above/below zero).
- **Story evolution:** Quality-LLM-generated summary per period (via OpenRouter) showing how the narrative's framing shifted. Weekly view: 1–2 sentences per week. Monthly view: a paragraph-level summary synthesized from weekly summaries. Quarterly view: a high-level arc description.
- **Top headlines:** 5 most representative headlines per period (closest to cluster centroid). Monthly and quarterly views show more headlines (10 and 5 respectively) to span the longer timeframe.
- **Linked tickers:** Tickers and sectors most frequently mentioned within this narrative (extracted from Finnhub's "related" field), showing which assets the market associates with this story.

### 4.4 Narrative Comparison (P1 — Should Have)

Overlay 2–4 narratives on a single chart to observe relationships. For example: do "recession fears" and "rate cut expectations" move together? Does "AI hype" crowd out "energy transition" coverage?

### 4.5 Emergence & Shift Alerts (P1)

Configurable alerts triggered when:

- **New narrative detected:** A cluster appears that doesn't match any existing narrative (cosine sim < 0.75 to all centroids).
- **Attention spike:** A narrative's z-score exceeds +2.0, meaning it's receiving 2 standard deviations more attention than its own recent baseline.
- **Mood reversal:** A narrative's sentiment flips sign and sustains for 2+ weeks.
- **Narrative exhaustion:** Share of attention drops below 2% for 3+ consecutive weeks after previously being above 10%.

### 4.6 Data Export & API (P2 — Nice to Have)

Expose narrative data as structured JSON for quant workflows. Fields per narrative per period: `narrative_id`, `label`, `article_count`, `share_of_attention`, `z_score`, `sentiment_mean`, `sentiment_std`, `top_tickers`, `representative_headlines`, `story_summary`. Queryable at weekly, monthly, or quarterly granularity. CSV and JSON export from dashboard.

---

## 5. Technical Architecture

### 5.1 Data Pipeline

Weekly batch pipeline (not real-time — intentionally coarse-grained to match the tool's purpose).

| Stage | Tool / Library | Input → Output | Schedule |
|---|---|---|---|
| **1. Ingest** | Finnhub general news endpoint (free tier) | API → raw headlines + summaries + sources + timestamps + related tickers | Weekly (Sunday night) |
| **2. Embed** | sentence-transformers (all-MiniLM-L6-v2 or FinBERT) | Text → 384-dim vectors | After ingest |
| **3. Cluster** | HDBSCAN (min_cluster_size=15, metric=cosine) | Vectors → cluster assignments | After embed |
| **4. Sentiment** | FinBERT (ProsusAI/finbert) or VADER + financial lexicon | Text → sentiment score [-1, +1] | After ingest |
| **5a. Label** | OpenRouter → Gemini Flash (cheap) | Top-10 headlines per cluster → short narrative label (3–6 words) | After cluster |
| **5b. Summarize** | OpenRouter → Sonnet / Gemini Pro (quality) | Week's headlines + prior summaries → story evolution summary (1–2 sentences). Also generates monthly summaries (from weekly summaries) and quarterly summaries (from monthly summaries) during aggregation. | After label |
| **6. Match** | Cosine similarity on cluster centroids | New clusters → matched to existing narratives or flagged as new | After label |
| **7. Store** | PostgreSQL + pgvector | All above → structured narrative records | After match |

### 5.2 Data Model (Core Tables)

**Critical principle:** All raw data is persisted permanently. Analysis can be re-run, models can be swapped, but original headlines are irreplaceable. The analysis layer (`narrative_weeks`) is a computed view that can be fully regenerated from raw data.

| Table | Key Fields | Granularity | Notes |
|---|---|---|---|
| **articles** (RAW — never modified) | `id`, `finnhub_id`, `headline`, `summary`, `source`, `url`, `published_at`, `related_tickers`, `category` | Per article | Immutable source of truth. Every headline ever ingested. ~100–180K for year 1. |
| **article_analysis** (COMPUTED) | `article_id`, `embedding` (384-dim), `sentiment_score`, `narrative_id`, `cluster_distance` | Per article | Can be regenerated. Links each article to its narrative. Stores embedding for re-clustering. |
| **narratives** | `id`, `label`, `first_seen`, `last_seen`, `status` (active/dormant), `centroid_embedding` | Per narrative | Long-lived entities. Label generated by cheap LLM. |
| **narrative_weeks** (COMPUTED) | `narrative_id`, `week_start`, `article_count`, `share_of_attention` (%), `z_score`, `sentiment_mean`, `sentiment_std`, `summary`, `top_headline_ids` | Per narrative per week | Primary analytics table. `share_of_attention` = this narrative's count / total articles that week. `z_score` recalculated across full history every run. |
| **narrative_months** (COMPUTED) | `narrative_id`, `month_start`, `article_count`, `share_of_attention` (%), `z_score`, `sentiment_mean`, `summary`, `top_headline_ids` | Per narrative per month | Aggregated from weekly data. Monthly summary generated by quality LLM from weekly summaries. Z-score baseline: trailing 6 months. |
| **narrative_quarters** (COMPUTED) | `narrative_id`, `quarter_start`, `article_count`, `share_of_attention` (%), `z_score`, `sentiment_mean`, `summary`, `top_headline_ids` | Per narrative per quarter | Aggregated from monthly data. Quarterly summary generated by quality LLM. Z-score baseline: trailing 4 quarters. |
| **narrative_tickers** | `narrative_id`, `week_start`, `ticker`, `mention_count` | Per narrative per ticker per week | Ticker-narrative linkage from Finnhub's "related" field. |
| **narrative_mutations** | `parent_id`, `child_id`, `mutation_date`, `description` | Per mutation event | Tracks narrative evolution and splits. |
| **weekly_totals** | `week_start`, `total_articles`, `total_clustered`, `total_noise` | Per week | Denominator for share-of-attention calculation. Tracks overall news volume. |
| **monthly_totals** (COMPUTED) | `month_start`, `total_articles`, `total_clustered`, `total_noise` | Per month | Aggregated from weekly_totals. Denominator for monthly share-of-attention. |
| **quarterly_totals** (COMPUTED) | `quarter_start`, `total_articles`, `total_clustered`, `total_noise` | Per quarter | Aggregated from monthly_totals. Denominator for quarterly share-of-attention. |

#### Recalibration Logic

Every time the pipeline runs, `share_of_attention` and `z_score` are recalculated across the entire timeline at all three granularities (weekly, monthly, quarterly), not just the new week. This means the full history is always internally consistent. Monthly and quarterly tables are derived from weekly data — they are roll-ups, not independent calculations. If the clustering model or parameters change, the entire analysis layer (`article_analysis`, `narrative_weeks`, `narrative_months`, `narrative_quarters`) can be regenerated from the immutable `articles` table. The raw data is the foundation; everything else is a view.

### 5.3 Tech Stack

Clean separation: Python backend (Claude Code) exposes a JSON API; Next.js frontend (Lovable/v0 for scaffolding, hand-tuned for custom viz) consumes it. Both can be rebuilt independently.

| Layer | Technology | Rationale |
|---|---|---|
| **Data Ingestion** | Python + Finnhub SDK (general news endpoint) | Single API, 1yr history, ~15–35 calls/week for incremental updates |
| **Embeddings** | sentence-transformers (HuggingFace) | Runs locally, no API costs. FinBERT for financial domain. |
| **Clustering** | HDBSCAN via hdbscan or sklearn | No need to pre-specify cluster count, handles noise articles |
| **Sentiment** | FinBERT (ProsusAI/finbert) or NLTK VADER | FinBERT preferred (finance-specific). VADER as lightweight fallback. |
| **LLM Gateway** | OpenRouter (openrouter.ai) | Single API key, swap models per task. Compare quality/cost without code changes. |
| **LLM — Labeling (cheap)** | Gemini 2.0 Flash via OpenRouter | Fast, cheap (~$0.10/1M tokens). Sufficient for short label generation. |
| **LLM — Summarization (quality)** | Claude Sonnet / Gemini Pro / GPT-4o-mini via OpenRouter | Needs comparative reasoning to describe narrative shifts. Test via OpenRouter. |
| **Database** | PostgreSQL + pgvector | pgvector for embedding similarity. Articles table is immutable source of truth. |
| **Backend API** | FastAPI (Python) | Lightweight JSON API. Same language as ML pipeline. Built with Claude Code. |
| **Frontend** | Next.js (React) + D3/Recharts | Scaffold with Lovable/v0. Hand-tune custom stream chart and z-score viz with D3. |
| **Scheduler** | cron (local) or GitHub Actions (free tier) | Weekly batch — no need for real-time infra |

### 5.4 Development Workflow

The frontend and backend are built with different tools, optimized for each:

- **Backend (Claude Code):** Data pipeline, Finnhub ingestion, embedding/clustering, DB management, FastAPI endpoints, OpenRouter integration, scheduling. Claude Code excels at structured Python backend work.
- **Frontend (Lovable / v0):** Scaffold layout, navigation, table views, forms, standard UI components. Lovable outputs Next.js code natively.
- **Custom viz (hand-tuned):** The 100% stacked stream chart, z-score anomaly chart, mood timeline, and story evolution timeline are bespoke D3/SVG components that will need manual refinement beyond what Lovable generates. These are the signature visualizations of the product.
- **Integration contract:** Backend exposes `/api/narratives`, `/api/narratives/{id}/weeks`, `/api/timeline?granularity=weekly|monthly|quarterly`, `/api/alerts` endpoints as JSON. The `granularity` parameter controls which aggregation table is queried. Frontend consumes them. Fully decoupled — either side can be rebuilt independently.

---

## 6. Data Source Strategy

**Single-source architecture:** Finnhub free tier only. Simplicity over coverage. One API key, one ingestion path, one rate limit to manage.

### 6.1 Finnhub General News Endpoint

The pipeline uses Finnhub's general market news endpoint (`/api/v1/news?category=general`), not the company-specific endpoint. This is the critical design choice: broad macro news captures the narratives we care about — Fed policy, geopolitics, sector rotation, macro risk themes — without needing to loop through individual tickers.

**Endpoint Details:**

- **Endpoint:** `GET /api/v1/news?category=general&minId=0`
- **Categories available:** general, forex, crypto, merger. We use "general" for broad macro coverage.
- **History:** Up to 1 year of historical articles via pagination (`minId` parameter).
- **Rate limit:** 60 calls/minute on free tier. Since we're pulling general news (not per-ticker), weekly ingestion requires only ~50–100 paginated calls — well within limits.
- **Fields returned:** `id`, `headline`, `summary`, `source`, `url`, `datetime`, `category`, `related` (tickers), `image`.

**What This Covers:**

Finnhub's general news feed aggregates from major financial newswires and publishers: Reuters, CNBC, Bloomberg syndication, MarketWatch, Financial Times syndication, WSJ syndication, and others. For macro narrative tracking, this single feed provides sufficient breadth. We are not trying to capture every article ever written — we need enough signal to detect and track narrative clusters over weeks.

**What This Doesn't Cover:**

This approach intentionally excludes company-specific earnings news, individual stock analysis, and niche sector coverage. If the tool proves valuable, a future version could add the company news endpoint (`/api/v1/company-news`) for ticker-level narrative tracking, or layer in additional sources. For now, simplicity wins.

### 6.2 Ingestion Volume Estimates

| Metric | Estimate | Notes |
|---|---|---|
| **Articles per day** | ~200–500 | General market news volume varies by news cycle |
| **Articles per week** | ~1,500–3,500 | Sufficient for robust weekly clustering |
| **Articles for 1-year backfill** | ~80,000–180,000 | One-time backfill, then weekly incremental |
| **API calls for backfill** | ~800–1,800 (paginated) | At 60/min, full backfill completes in ~30 min |
| **API calls per weekly update** | ~15–35 | Trivial. Completes in seconds. |

---

## 7. Development Milestones

| Phase | Milestone | Deliverables | Duration |
|---|---|---|---|
| **Phase 0** | Pipeline Proof | Ingest 3 months of news for 50 tickers. Embed + cluster. Verify narratives make sense manually. | 1–2 weeks |
| **Phase 1** | Core MVP | Full pipeline (ingest → embed → cluster → label → store). Streamlit dashboard with narrative timeline + detail view. Weekly cron. | 3–4 weeks |
| **Phase 2** | Polish & Alerts | Narrative comparison view. Emergence + mood-shift alerts (email or Slack webhook). Narrative mutation tracking. | 2–3 weeks |
| **Phase 3** | Scale & Export | Expand to full S&P 500. JSON API for quant consumption. Additional data sources. React frontend upgrade. | 4–6 weeks |

---

## 8. Key Design Decisions & Trade-offs

### 8.1 Weekly, Not Daily

This is intentional, not a limitation. Daily granularity adds noise and makes narrative detection fragile (small sample sizes per cluster per day). Weekly aggregation gives robust clusters and matches the tool's purpose: observing long-term evolution. Users who want daily sentiment already have Bloomberg/Refinitiv.

### 8.2 Full-History Recalibration on Every Run

Every weekly pipeline run recalculates `share_of_attention` and `z_score` across the entire timeline at all granularities (weekly, monthly, quarterly), not just the latest week. This means historical values shift as the baseline evolves. If inflation coverage was steady for 9 months then spiked, the z-score for the spike week is calculated against those 9 months of stability. If coverage later normalizes, early weeks' z-scores adjust accordingly.

This is intentional. A static snapshot would miss the context: "25% share of attention for inflation" means nothing without knowing the baseline was 10%. Recalibration ensures every data point is always viewed in the context of the full available history. The cost is that the analysis layer (`article_analysis` + `narrative_weeks` + `narrative_months` + `narrative_quarters`) must be regenerable from raw data, which the immutable `articles` table guarantees.

Monthly and quarterly views are not just cosmetic re-binning — they use granularity-appropriate z-score baselines (6 months and 4 quarters respectively) and their own LLM-generated summaries that synthesize the finer-grained summaries into higher-level narrative arcs.

### 8.3 Unsupervised Discovery, Not Predefined Categories

We let narratives emerge from the data rather than tracking a fixed list of themes. This catches surprises — narratives you didn't know to look for. The cost is occasional noise clusters, mitigated by the `min_cluster_size` threshold and LLM-based quality filtering.

### 8.4 Two-Model LLM Strategy via OpenRouter

The pipeline has two fundamentally different LLM tasks. Labeling is pattern recognition: given 10 headlines, output 3–6 words. A cheap, fast model (Gemini Flash at ~$0.10/1M tokens) handles this well. Story evolution summarization is comparative reasoning: given this week's headlines and last week's summary, describe what changed. This requires a smarter model (Sonnet, Gemini Pro, or GPT-4o-mini).

OpenRouter acts as the single gateway. One API key, one SDK, one code path. Swapping models is a config change, not a code change. This enables A/B testing: run the same week's data through Gemini Flash vs. Haiku vs. Llama for labeling, compare quality, pick the best cost/quality ratio. The same applies to summarization. OpenRouter's unified billing also simplifies cost tracking.

### 8.5 Cosine Similarity for Narrative Continuity

Matching weekly clusters to existing narratives via centroid similarity (threshold 0.75) is simple and effective. The alternative — topic models like LDA — is less stable week-to-week. The 0.75 threshold is tunable: lower catches more mutations, higher demands stricter continuity.

### 8.6 Headline-Level, Not Full-Article

Headlines + snippets are sufficient for narrative identification and significantly cheaper to process than full articles. Full-text analysis is a potential Phase 3 enhancement if users want deeper story extraction.

---

## 9. Risks & Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| **Finnhub free tier rate limits or policy changes** | Single point of failure — pipeline breaks if API changes | Archive all raw data locally on every pull. If Finnhub changes, historical data is preserved. Ingestion layer is isolated — swapping to a different API later requires changing only one module. |
| **Noisy / meaningless clusters** | User sees junk narratives, loses trust | LLM-based quality filter: ask model to rate each cluster's coherence 1–5, suppress <3. Tune `min_cluster_size`. |
| **Narrative drift / false continuity** | Two different stories get merged into one narrative | Lower cosine threshold (0.80), add LLM validation step to confirm semantic continuity. |
| **Embedding model bias** | General-purpose embeddings may miss financial nuance | Start with general model, benchmark against FinBERT, switch if financial-domain model performs better on manual evaluation. |
| **LLM costs for labeling/summarization** | Cost creep as narrative count grows | Two-tier model strategy via OpenRouter: Gemini Flash for cheap labeling, smarter model only for summaries. Batch calls. Monitor per-model spend in OpenRouter dashboard. |

---

## 10. Success Metrics

- **Narrative coherence:** Manual review of top-20 narratives per month — target ≥80% rated as coherent and genuinely distinct themes.
- **Emergence detection:** Tool identifies narratives at least 2 weeks before they peak in mainstream coverage (measured via Google Trends or similar).
- **Coverage stability:** Pipeline runs without failure for 8+ consecutive weeks.
- **User engagement:** Weekly active usage (dashboard visits) by at least 1 active user within 4 weeks of MVP.

---

## 11. Open Questions

- **Optimal embedding model:** Should we benchmark all-MiniLM-L6-v2 vs. FinBERT vs. OpenAI ada-002 on a manually labeled test set before committing?
- **OpenRouter model selection:** Run Phase 0 with 3–4 candidate models per task (labeling: Gemini Flash, Haiku, Llama 3; summarization: Sonnet, Gemini Pro, GPT-4o-mini). Score output quality on 50 test clusters before committing.
- **Narrative granularity:** Is "Fed policy" one narrative or should "rate hikes," "rate cuts," and "QT taper" be separate? This is a `min_cluster_size` tuning question.
- **Narrative hierarchy:** Should we support parent/child narrative relationships? E.g., "Trade policy" as a parent containing "China tariffs," "EU trade deal," and "reshoring." Or keep it flat?
- **Duplicate detection:** Finnhub general news may return the same story from multiple outlets. Should we deduplicate before clustering (cosine sim > 0.95 on embeddings), or let HDBSCAN naturally absorb them?
- **Deployment target:** Local-only (laptop) or deploy to a free-tier cloud (Railway, Render, Fly.io)?