# Phase 1 Design: Streamlit Dashboard

**Date:** 2026-03-01
**Goal:** Streamlit app that visualizes pipeline narratives — timeline chart, detail view, pipeline trigger.

## Architecture

Streamlit app reads directly from SQLite (`data/narratio.db`). No API layer — shares the same Python package as the pipeline.

## Views

### Sidebar Controls
- Chart mode toggle: Share of Attention vs Z-Score
- Time range slider
- Narrative filter (multi-select)
- "Run Pipeline" button (triggers full pipeline)

### Timeline View (main area)
- **Share of Attention mode:** 100% stacked area chart (Plotly). Each narrative = colored band. Y-axis 0-100%.
- **Z-Score mode:** Multi-line chart. Each narrative = line. Horizontal bands at ±1.5 and ±2.0.
- Built with Plotly for native Streamlit interactivity.

### Narrative Detail (select from dropdown or click table row)
- Summary panel: label, share of attention, z-score, sentiment, date range
- Weekly LLM summary text
- Top 5 headlines
- Sentiment trend mini-chart

### Overview Table
- All narratives ranked by article count with key metrics

## Tech
- Plotly for charts (native Streamlit support)
- SQLite direct reads (no API)
- Single-page app with sidebar controls

## Dependencies
- streamlit
- plotly
- pandas
