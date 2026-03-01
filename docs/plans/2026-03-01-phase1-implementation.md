# Phase 1: Streamlit Dashboard Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a Streamlit dashboard that visualizes discovered narratives with timeline charts, detail views, and a pipeline trigger button.

**Architecture:** Single Streamlit app (`narratio/app.py`) reads directly from the existing SQLite database. A data access layer (`narratio/data.py`) provides pandas DataFrames to the UI. Plotly renders all charts. Sidebar controls toggle between Share of Attention (stacked area) and Z-Score (multi-line) views.

**Tech Stack:** Streamlit, Plotly, pandas (all new deps added to pyproject.toml)

---

### Task 1: Add Dependencies

**Files:**
- Modify: `pyproject.toml`

**Step 1: Add streamlit, plotly, pandas to dependencies**

In `pyproject.toml`, update the `dependencies` list to add:

```toml
dependencies = [
    "finnhub-python>=2.4.20",
    "httpx>=0.27",
    "hdbscan>=0.8.40",
    "numpy>=2.0",
    "scikit-learn>=1.5",
    "python-dotenv>=1.0",
    "rich>=13.0",
    "streamlit>=1.41",
    "plotly>=6.0",
    "pandas>=2.2",
]
```

**Step 2: Sync**

```bash
uv sync
```

**Step 3: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "feat: add streamlit, plotly, pandas dependencies"
```

---

### Task 2: Data Access Layer

**Files:**
- Create: `narratio/data.py`
- Create: `tests/test_data.py`

**Step 1: Write the failing test**

```python
import pandas as pd
from narratio.db import init_db, get_connection
from narratio.data import (
    get_narratives_df,
    get_timeline_df,
    get_narrative_detail,
    get_narrative_headlines,
)


def _seed_db(db_path):
    """Seed a test database with 2 narratives across 3 weeks."""
    init_db(db_path)
    conn = get_connection(db_path)

    # 2 narratives
    conn.execute(
        "INSERT INTO narratives (id, label, first_seen, last_seen, status) VALUES (1, 'Fed Rate Cuts', '2025-12-01', '2025-12-22', 'active')"
    )
    conn.execute(
        "INSERT INTO narratives (id, label, first_seen, last_seen, status) VALUES (2, 'AI Hype Cycle', '2025-12-01', '2025-12-22', 'active')"
    )

    # Weekly data for narrative 1
    for i, ws in enumerate(["2025-12-01", "2025-12-08", "2025-12-15"]):
        conn.execute(
            """INSERT INTO narrative_weeks (narrative_id, week_start, article_count, share_of_attention, z_score, sentiment_mean, summary, top_headline_ids)
               VALUES (1, ?, ?, ?, ?, ?, ?, ?)""",
            (ws, 20 + i * 5, 15.0 + i * 5, 0.5 + i * 0.3, 0.3, f"Fed summary week {i+1}", "[1,2,3]"),
        )

    # Weekly data for narrative 2
    for i, ws in enumerate(["2025-12-01", "2025-12-08", "2025-12-15"]):
        conn.execute(
            """INSERT INTO narrative_weeks (narrative_id, week_start, article_count, share_of_attention, z_score, sentiment_mean, summary, top_headline_ids)
               VALUES (2, ?, ?, ?, ?, ?, ?, ?)""",
            (ws, 30 - i * 5, 25.0 - i * 5, -0.2 + i * 0.1, -0.1, f"AI summary week {i+1}", "[4,5,6]"),
        )

    # Weekly totals
    for ws in ["2025-12-01", "2025-12-08", "2025-12-15"]:
        conn.execute(
            "INSERT INTO weekly_totals (week_start, total_articles, total_clustered, total_noise) VALUES (?, 200, 150, 50)",
            (ws,),
        )

    # Articles for headlines
    for i in range(6):
        nar_id = 1 if i < 3 else 2
        conn.execute(
            """INSERT INTO articles (finnhub_id, headline, summary, source, url, published_at, category)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (i, f"Headline {i} for narrative {nar_id}", f"Summary {i}", "reuters", "http://example.com", 1733011200 + i * 86400, "general"),
        )
        conn.execute(
            "INSERT INTO article_analysis (article_id, narrative_id, sentiment_score, sentiment_label) VALUES (?, ?, ?, ?)",
            (i + 1, nar_id, 0.3 if nar_id == 1 else -0.1, "bullish" if nar_id == 1 else "neutral"),
        )

    conn.commit()
    conn.close()


def test_get_narratives_df(tmp_path):
    db_path = str(tmp_path / "test.db")
    _seed_db(db_path)

    df = get_narratives_df(db_path)
    assert isinstance(df, pd.DataFrame)
    assert len(df) == 2
    assert "label" in df.columns
    assert "article_count" in df.columns


def test_get_timeline_df(tmp_path):
    db_path = str(tmp_path / "test.db")
    _seed_db(db_path)

    df = get_timeline_df(db_path)
    assert isinstance(df, pd.DataFrame)
    assert len(df) == 6  # 2 narratives * 3 weeks
    assert "week_start" in df.columns
    assert "share_of_attention" in df.columns
    assert "label" in df.columns


def test_get_narrative_detail(tmp_path):
    db_path = str(tmp_path / "test.db")
    _seed_db(db_path)

    detail = get_narrative_detail(db_path, 1)
    assert detail["label"] == "Fed Rate Cuts"
    assert len(detail["weeks"]) == 3


def test_get_narrative_headlines(tmp_path):
    db_path = str(tmp_path / "test.db")
    _seed_db(db_path)

    headlines = get_narrative_headlines(db_path, 1, limit=5)
    assert len(headlines) >= 1
    assert "headline" in headlines[0]
```

**Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_data.py -v
```

Expected: FAIL — `ImportError`

**Step 3: Implement data.py**

```python
"""Data access layer — returns pandas DataFrames from SQLite for Streamlit."""

import pandas as pd
from narratio.db import get_connection


def get_narratives_df(db_path: str) -> pd.DataFrame:
    conn = get_connection(db_path)
    df = pd.read_sql_query(
        """SELECT n.id, n.label, n.first_seen, n.last_seen, n.status,
                  COUNT(aa.article_id) as article_count
           FROM narratives n
           LEFT JOIN article_analysis aa ON aa.narrative_id = n.id
           GROUP BY n.id
           ORDER BY article_count DESC""",
        conn,
    )
    conn.close()
    return df


def get_timeline_df(db_path: str) -> pd.DataFrame:
    conn = get_connection(db_path)
    df = pd.read_sql_query(
        """SELECT nw.narrative_id, n.label, nw.week_start,
                  nw.article_count, nw.share_of_attention,
                  nw.z_score, nw.sentiment_mean
           FROM narrative_weeks nw
           JOIN narratives n ON n.id = nw.narrative_id
           ORDER BY nw.week_start, nw.share_of_attention DESC""",
        conn,
    )
    conn.close()
    df["week_start"] = pd.to_datetime(df["week_start"])
    return df


def get_narrative_detail(db_path: str, narrative_id: int) -> dict:
    conn = get_connection(db_path)

    narrative = conn.execute(
        "SELECT * FROM narratives WHERE id = ?", (narrative_id,)
    ).fetchone()

    weeks = conn.execute(
        """SELECT * FROM narrative_weeks
           WHERE narrative_id = ?
           ORDER BY week_start""",
        (narrative_id,),
    ).fetchall()

    conn.close()

    return {
        "id": narrative["id"],
        "label": narrative["label"],
        "first_seen": narrative["first_seen"],
        "last_seen": narrative["last_seen"],
        "status": narrative["status"],
        "weeks": [dict(w) for w in weeks],
    }


def get_narrative_headlines(db_path: str, narrative_id: int, limit: int = 10) -> list[dict]:
    conn = get_connection(db_path)
    rows = conn.execute(
        """SELECT a.headline, a.source, a.url, a.published_at,
                  aa.sentiment_score, aa.sentiment_label
           FROM articles a
           JOIN article_analysis aa ON aa.article_id = a.id
           WHERE aa.narrative_id = ?
           ORDER BY a.published_at DESC
           LIMIT ?""",
        (narrative_id, limit),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]
```

**Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_data.py -v
```

Expected: 4 passed.

**Step 5: Commit**

```bash
git add narratio/data.py tests/test_data.py
git commit -m "feat: data access layer returning pandas DataFrames"
```

---

### Task 3: Streamlit App — Timeline Charts

**Files:**
- Create: `narratio/app.py`

This task creates the main Streamlit app with sidebar controls and the two timeline chart modes. No tests for Streamlit UI — verified visually.

**Step 1: Create narratio/app.py**

```python
"""Streamlit dashboard for Narratio."""

import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path

from narratio.data import get_narratives_df, get_timeline_df, get_narrative_detail, get_narrative_headlines

# Default DB path
DB_PATH = str(Path(__file__).parent.parent / "data" / "narratio.db")

st.set_page_config(page_title="Narratio", page_icon="📡", layout="wide")


def main():
    st.title("Narratio — Narrative Radar")
    st.caption("Track the stories markets tell themselves")

    if not Path(DB_PATH).exists():
        st.error("No database found. Run the pipeline first: `uv run narratio`")
        return

    # --- Sidebar ---
    with st.sidebar:
        st.header("Controls")

        chart_mode = st.radio(
            "Chart Mode",
            ["Share of Attention", "Z-Score Anomaly"],
            index=0,
        )

        # Load data
        narratives_df = get_narratives_df(DB_PATH)
        timeline_df = get_timeline_df(DB_PATH)

        if timeline_df.empty:
            st.warning("No narrative data yet. Run the pipeline first.")
            return

        # Time range
        all_weeks = sorted(timeline_df["week_start"].unique())
        if len(all_weeks) > 1:
            week_range = st.select_slider(
                "Time Range",
                options=all_weeks,
                value=(all_weeks[0], all_weeks[-1]),
                format_func=lambda x: x.strftime("%Y-%m-%d"),
            )
            timeline_df = timeline_df[
                (timeline_df["week_start"] >= week_range[0])
                & (timeline_df["week_start"] <= week_range[1])
            ]

        # Narrative filter
        all_labels = sorted(timeline_df["label"].unique())
        selected = st.multiselect(
            "Filter Narratives",
            options=all_labels,
            default=all_labels,
        )
        if selected:
            timeline_df = timeline_df[timeline_df["label"].isin(selected)]

        st.divider()

        # Pipeline trigger
        if st.button("Run Pipeline", type="primary", use_container_width=True):
            _run_pipeline()

    # --- Main area ---
    if timeline_df.empty:
        st.info("No data for selected filters.")
        return

    # Timeline chart
    if chart_mode == "Share of Attention":
        _render_attention_chart(timeline_df)
    else:
        _render_zscore_chart(timeline_df)

    st.divider()

    # Narrative detail section
    _render_narrative_details(narratives_df)


def _render_attention_chart(df):
    """100% stacked area chart of share of attention."""
    fig = px.area(
        df,
        x="week_start",
        y="share_of_attention",
        color="label",
        groupnorm="percent",
        labels={
            "week_start": "Week",
            "share_of_attention": "Share of Attention (%)",
            "label": "Narrative",
        },
    )
    fig.update_layout(
        yaxis_title="Share of Attention (%)",
        xaxis_title="Week",
        legend_title="Narrative",
        hovermode="x unified",
        height=500,
    )
    st.plotly_chart(fig, use_container_width=True)


def _render_zscore_chart(df):
    """Multi-line z-score chart with threshold bands."""
    fig = go.Figure()

    # Threshold bands
    fig.add_hrect(y0=1.5, y1=2.0, fillcolor="orange", opacity=0.1, line_width=0)
    fig.add_hrect(y0=2.0, y1=4.0, fillcolor="red", opacity=0.1, line_width=0)
    fig.add_hrect(y0=-2.0, y1=-1.5, fillcolor="orange", opacity=0.1, line_width=0)
    fig.add_hrect(y0=-4.0, y1=-2.0, fillcolor="red", opacity=0.1, line_width=0)
    fig.add_hline(y=0, line_dash="dash", line_color="gray", opacity=0.5)

    for label in df["label"].unique():
        narrative_df = df[df["label"] == label]
        fig.add_trace(go.Scatter(
            x=narrative_df["week_start"],
            y=narrative_df["z_score"],
            mode="lines+markers",
            name=label,
            hovertemplate="%{y:.2f}",
        ))

    fig.update_layout(
        yaxis_title="Z-Score",
        xaxis_title="Week",
        legend_title="Narrative",
        hovermode="x unified",
        height=500,
    )
    st.plotly_chart(fig, use_container_width=True)


def _render_narrative_details(narratives_df):
    """Render narrative overview table and expandable details."""
    st.subheader("Narratives")

    if narratives_df.empty:
        return

    # Overview table
    display_df = narratives_df[["label", "article_count", "first_seen", "last_seen", "status"]].copy()
    display_df.columns = ["Narrative", "Articles", "First Seen", "Last Seen", "Status"]
    st.dataframe(display_df, use_container_width=True, hide_index=True)

    # Detail expanders
    for _, row in narratives_df.iterrows():
        narrative_id = row["id"]
        with st.expander(f"**{row['label']}** — {row['article_count']} articles"):
            detail = get_narrative_detail(DB_PATH, narrative_id)
            headlines = get_narrative_headlines(DB_PATH, narrative_id, limit=5)

            if detail["weeks"]:
                latest = detail["weeks"][-1]

                col1, col2, col3, col4 = st.columns(4)
                col1.metric("Share of Attention", f"{latest.get('share_of_attention', 0):.1f}%")
                col2.metric("Z-Score", f"{latest.get('z_score', 0):.2f}" if latest.get('z_score') is not None else "N/A")
                col3.metric("Sentiment", f"{latest.get('sentiment_mean', 0):.2f}" if latest.get('sentiment_mean') is not None else "N/A")
                col4.metric("Articles (latest week)", latest.get("article_count", 0))

                # Summary
                if latest.get("summary"):
                    st.markdown(f"**Latest Summary:** {latest['summary']}")

                # Sentiment mini-chart
                if len(detail["weeks"]) > 1:
                    import pandas as pd
                    weeks_df = pd.DataFrame(detail["weeks"])
                    weeks_df["week_start"] = pd.to_datetime(weeks_df["week_start"])
                    fig = px.line(
                        weeks_df,
                        x="week_start",
                        y="sentiment_mean",
                        labels={"week_start": "Week", "sentiment_mean": "Sentiment"},
                    )
                    fig.add_hline(y=0, line_dash="dash", line_color="gray", opacity=0.5)
                    fig.update_layout(height=200, margin=dict(l=0, r=0, t=10, b=0))
                    st.plotly_chart(fig, use_container_width=True)

            # Headlines
            if headlines:
                st.markdown("**Top Headlines:**")
                for h in headlines:
                    from datetime import datetime, timezone
                    dt = datetime.fromtimestamp(h["published_at"], tz=timezone.utc).strftime("%b %d")
                    sentiment_icon = "🟢" if (h.get("sentiment_score") or 0) > 0.2 else "🔴" if (h.get("sentiment_score") or 0) < -0.2 else "⚪"
                    st.markdown(f"- {sentiment_icon} [{h['headline']}]({h['url']}) — *{h['source']}, {dt}*")


def _run_pipeline():
    """Run the full pipeline from within Streamlit."""
    with st.spinner("Running pipeline..."):
        try:
            from narratio.config import get_config
            from narratio.pipeline import run_pipeline

            cfg = get_config()
            run_pipeline(
                finnhub_key=cfg.finnhub_api_key,
                openrouter_key=cfg.openrouter_api_key,
                db_path=DB_PATH,
                embeddings_path=cfg.embeddings_path,
                max_pages=5,
            )
            st.success("Pipeline complete! Refresh to see updated data.")
            st.rerun()
        except Exception as e:
            st.error(f"Pipeline failed: {e}")


if __name__ == "__main__":
    main()
```

**Step 2: Verify it runs**

```bash
uv run streamlit run narratio/app.py
```

Open browser to http://localhost:8501. Verify:
- Page loads without errors
- Timeline chart renders (if data exists)
- Sidebar controls work
- Narrative expanders show details

**Step 3: Commit**

```bash
git add narratio/app.py
git commit -m "feat: Streamlit dashboard with timeline charts and detail views"
```

---

### Task 4: Streamlit Entry Point

**Files:**
- Modify: `pyproject.toml`

**Step 1: Add streamlit script entry**

Add to `pyproject.toml` under `[project.scripts]`:

```toml
[project.scripts]
narratio = "narratio.pipeline:main"
narratio-app = "narratio._run_app:main"
```

**Step 2: Create the thin runner**

Create `narratio/_run_app.py`:

```python
"""Streamlit app launcher."""

import subprocess
import sys
from pathlib import Path


def main():
    app_path = Path(__file__).parent / "app.py"
    subprocess.run([sys.executable, "-m", "streamlit", "run", str(app_path)], check=True)
```

**Step 3: Sync and test**

```bash
uv sync
uv run narratio-app
```

Verify the Streamlit app launches.

**Step 4: Commit**

```bash
git add pyproject.toml narratio/_run_app.py
git commit -m "feat: narratio-app CLI entry point for Streamlit dashboard"
```
