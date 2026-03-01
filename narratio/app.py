"""Streamlit dashboard for Narratio."""

import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from datetime import datetime, timezone
from pathlib import Path

from narratio.data import (
    get_narratives_df,
    get_timeline_df,
    get_narrative_detail,
    get_narrative_headlines,
)

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

        if st.button("Run Pipeline", type="primary", use_container_width=True):
            _run_pipeline()

    # --- Main area ---
    if timeline_df.empty:
        st.info("No data for selected filters.")
        return

    if chart_mode == "Share of Attention":
        _render_attention_chart(timeline_df)
    else:
        _render_zscore_chart(timeline_df)

    st.divider()
    _render_narrative_details(narratives_df)


def _render_attention_chart(df):
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
    fig = go.Figure()

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
    st.subheader("Narratives")

    if narratives_df.empty:
        return

    display_df = narratives_df[["label", "article_count", "first_seen", "last_seen", "status"]].copy()
    display_df.columns = ["Narrative", "Articles", "First Seen", "Last Seen", "Status"]
    st.dataframe(display_df, use_container_width=True, hide_index=True)

    for _, row in narratives_df.iterrows():
        narrative_id = row["id"]
        with st.expander(f"**{row['label']}** — {row['article_count']} articles"):
            detail = get_narrative_detail(DB_PATH, narrative_id)
            headlines = get_narrative_headlines(DB_PATH, narrative_id, limit=5)

            if detail["weeks"]:
                latest = detail["weeks"][-1]

                col1, col2, col3, col4 = st.columns(4)
                col1.metric("Share of Attention", f"{latest.get('share_of_attention', 0):.1f}%")
                col2.metric(
                    "Z-Score",
                    f"{latest.get('z_score', 0):.2f}" if latest.get("z_score") is not None else "N/A",
                )
                col3.metric(
                    "Sentiment",
                    f"{latest.get('sentiment_mean', 0):.2f}" if latest.get("sentiment_mean") is not None else "N/A",
                )
                col4.metric("Articles (latest week)", latest.get("article_count", 0))

                if latest.get("summary"):
                    st.markdown(f"**Latest Summary:** {latest['summary']}")

                if len(detail["weeks"]) > 1:
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

            if headlines:
                st.markdown("**Top Headlines:**")
                for h in headlines:
                    dt = datetime.fromtimestamp(h["published_at"], tz=timezone.utc).strftime("%b %d")
                    score = h.get("sentiment_score") or 0
                    icon = "🟢" if score > 0.2 else "🔴" if score < -0.2 else "⚪"
                    st.markdown(f"- {icon} [{h['headline']}]({h['url']}) — *{h['source']}, {dt}*")


def _run_pipeline():
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
            st.success("Pipeline complete! Refreshing...")
            st.rerun()
        except Exception as e:
            st.error(f"Pipeline failed: {e}")


if __name__ == "__main__":
    main()
