"""Main pipeline orchestrator."""

import logging
import os
import sys
from collections.abc import Callable
from datetime import datetime, timezone
import numpy as np
from rich.console import Console

logger = logging.getLogger(__name__)

from narratio.config import Config, get_config
from narratio.db import init_db
from narratio.ingest import ingest_month as ingest_nyt_month
from narratio.ingest_guardian import ingest_month as ingest_guardian_month
from narratio.embed import embed_articles
from narratio.cluster import cluster_articles, merge_clusters, filter_relevance
from narratio.sentiment import analyze_sentiment
from narratio.label import label_clusters
from narratio.summarize import compute_weekly_analytics, generate_weekly_summaries
from narratio.data import compute_significance_scores
from narratio.report import generate_report


def run_analysis(
    cfg: Config,
    progress_callback: "Callable[[int, str], None] | None" = None,
) -> None:
    """Run the analysis pipeline:
    Embed → Filter Relevance → Cluster → Merge Clusters → Sentiment →
    Label (many-to-one) → Enforce Narrative Cap → Analytics → Significance → Summarize

    Can be called independently of ingestion, e.g. from backfill.py.
    progress_callback receives (step_number, step_label) before each step.
    """
    console = Console()
    cb = progress_callback or (lambda step, label: None)
    db_path = cfg.db_path
    embeddings_path = cfg.embeddings_path

    cb(1, "Extracting country mentions...")
    console.print("\n[bold]1/10 Extracting country mentions...[/bold]")
    n_countries = _extract_article_countries(db_path)
    console.print(f"  Processed {n_countries} articles")

    cb(2, "Generating embeddings...")
    console.print("\n[bold]2/10 Generating embeddings...[/bold]")
    _ensure_analysis_rows(db_path)
    count = embed_articles(db_path, embeddings_path, cfg.openrouter_api_key, model=cfg.embed_model)
    console.print(f"  Embedded {count} articles")

    # Load embeddings once for all clustering steps
    emb = np.load(embeddings_path) if os.path.exists(embeddings_path) else None

    cb(3, "Filtering relevance...")
    console.print("\n[bold]3/10 Filtering relevance...[/bold]")
    n_irrelevant = filter_relevance(db_path, embeddings_path, relevance_threshold=cfg.relevance_threshold, embeddings=emb)
    console.print(f"  Marked {n_irrelevant} articles as irrelevant")

    cb(4, "Clustering articles...")
    console.print("\n[bold]4/10 Clustering articles...[/bold]")
    n_clusters = cluster_articles(
        db_path, embeddings_path,
        min_cluster_size=cfg.min_cluster_size,
        min_samples=cfg.min_samples,
        umap_n_components=cfg.umap_n_components,
        umap_n_neighbors=cfg.umap_n_neighbors,
        umap_min_dist=cfg.umap_min_dist,
        embeddings=emb,
    )
    console.print(f"  Found {n_clusters} raw clusters")

    cb(5, "Merging clusters...")
    console.print("\n[bold]5/10 Merging similar clusters...[/bold]")
    n_merged = merge_clusters(db_path, embeddings_path, merge_threshold=cfg.merge_threshold, embeddings=emb)
    console.print(f"  Merged to {n_merged} clusters")

    cb(6, "Analyzing sentiment...")
    console.print("\n[bold]6/10 Analyzing sentiment...[/bold]")
    count = analyze_sentiment(db_path, cfg.openrouter_api_key, model=cfg.sentiment_model)
    console.print(f"  Scored {count} articles")

    cb(7, "Labeling narratives...")
    console.print("\n[bold]7/10 Labeling narratives...[/bold]")
    n_narratives = label_clusters(
        db_path, embeddings_path, cfg.openrouter_api_key,
        match_threshold=cfg.match_threshold,
        max_narratives=cfg.max_narratives,
        label_model=cfg.label_model,
    )
    console.print(f"  Labeled {n_narratives} new narratives")

    cb(8, "Computing weekly analytics...")
    console.print("\n[bold]8/10 Computing weekly analytics...[/bold]")
    n_weeks = compute_weekly_analytics(db_path, z_score_window=cfg.z_score_window)
    console.print(f"  Computed analytics for {n_weeks} narrative-weeks")

    cb(9, "Computing significance scores...")
    console.print("\n[bold]9/10 Computing significance scores...[/bold]")
    n_scored = compute_significance_scores(db_path)
    console.print(f"  Scored {n_scored} narratives")

    cb(10, "Generating summaries...")
    console.print("\n[bold]10/10 Generating LLM summaries (top narratives)...[/bold]")
    n_summaries = generate_weekly_summaries(
        db_path, cfg.openrouter_api_key,
        top_n=cfg.summary_top_n,
        model=cfg.summary_model,
    )
    console.print(f"  Generated {n_summaries} weekly summaries")

    console.print("\n" + "=" * 40)
    report = generate_report(db_path)
    console.print(report)


def run_pipeline(
    cfg: Config,
    year: int | None = None,
    month: int | None = None,
    progress_callback: "Callable[[int, str], None] | None" = None,
) -> None:
    console = Console()
    cb = progress_callback or (lambda step, label: None)
    now = datetime.now(timezone.utc)
    if year is None:
        year = now.year
    if month is None:
        month = now.month

    logger.info("Starting pipeline for %d-%02d", year, month)
    console.print("[bold cyan]Narratio Pipeline[/bold cyan]")
    console.print("=" * 40)

    cb(1, "Initializing database...")
    console.print("\n[bold]1/13 Initializing database...[/bold]")
    init_db(cfg.db_path)
    console.print("  Done")

    # --- Ingest from all available sources ---
    cb(2, "Ingesting articles...")
    console.print(f"\n[bold]2/13 Ingesting articles ({year}-{month:02d})...[/bold]")
    total_ingested = 0

    if cfg.nyt_api_key:
        console.print("  [dim]NYT Archive API...[/dim]")
        count = ingest_nyt_month(cfg.db_path, cfg.nyt_api_key, year, month)
        console.print(f"  NYT: {count} new articles")
        total_ingested += count

    if cfg.guardian_api_key:
        console.print("  [dim]Guardian Open Platform...[/dim]")
        count = ingest_guardian_month(cfg.db_path, cfg.guardian_api_key, year, month)
        console.print(f"  Guardian: {count} new articles")
        total_ingested += count

    if total_ingested == 0 and not cfg.nyt_api_key and not cfg.guardian_api_key:
        console.print("  [red]No API keys configured. Set NYT_API_KEY and/or GUARDIAN_API_KEY.[/red]")
        return

    console.print(f"  [bold]Total: {total_ingested} new articles[/bold]")

    # --- Scrape Economist covers (non-blocking) ---
    cb(3, "Scraping Economist covers...")
    console.print("\n[bold]3/13 Scraping Economist covers...[/bold]")
    try:
        from narratio.scrape_covers import scrape_covers
        n_covers = scrape_covers(cfg.db_path, year=year)
        console.print(f"  Found {n_covers} covers")
    except Exception as e:
        console.print(f"  [dim]Skipped (Playwright not available or scrape failed: {e})[/dim]")

    # --- Run analysis pipeline (steps 4-12) ---
    def _offset_cb(step: int, label: str) -> None:
        cb(step + 3, label)

    run_analysis(cfg, progress_callback=_offset_cb)


def _extract_article_countries(db_path: str) -> int:
    """Extract country mentions from articles not yet in article_countries."""
    from narratio.countries import extract_countries
    from narratio.db import get_connection

    conn = get_connection(db_path)
    rows = conn.execute(
        """SELECT a.id, a.headline, a.summary FROM articles a
           WHERE a.id NOT IN (SELECT DISTINCT article_id FROM article_countries)"""
    ).fetchall()
    if not rows:
        conn.close()
        return 0

    inserts = []
    for row in rows:
        codes = extract_countries(row["headline"], row["summary"] or "")
        for code in codes:
            inserts.append((row["id"], code))

    if inserts:
        conn.executemany(
            "INSERT OR IGNORE INTO article_countries (article_id, country_code) VALUES (?, ?)",
            inserts,
        )
        conn.commit()
    conn.close()
    return len(rows)


def _ensure_analysis_rows(db_path: str) -> None:
    from narratio.db import get_connection
    conn = get_connection(db_path)
    conn.execute(
        """INSERT OR IGNORE INTO article_analysis (article_id)
           SELECT id FROM articles WHERE id NOT IN (SELECT article_id FROM article_analysis)"""
    )
    conn.commit()
    conn.close()


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    try:
        cfg = get_config()
    except ValueError as e:
        print(f"Error: {e}")
        print("Copy .env.example to .env and fill in your API keys.")
        sys.exit(1)

    run_pipeline(cfg)


if __name__ == "__main__":
    main()
