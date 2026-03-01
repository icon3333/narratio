"""Main pipeline orchestrator."""

import sys
import finnhub
from rich.console import Console

from narratio.config import get_config
from narratio.db import init_db
from narratio.ingest import ingest_articles
from narratio.embed import embed_articles
from narratio.cluster import cluster_articles
from narratio.sentiment import analyze_sentiment
from narratio.label import label_clusters
from narratio.summarize import summarize_narratives
from narratio.report import generate_report


def run_pipeline(
    finnhub_key: str,
    openrouter_key: str,
    db_path: str = "data/narratio.db",
    embeddings_path: str = "data/embeddings.npy",
    max_pages: int = 100,
) -> None:
    """Run the full Narratio pipeline end-to-end."""
    console = Console()

    console.print("[bold cyan]Narratio Pipeline[/bold cyan]")
    console.print("=" * 40)

    # 1. Init DB
    console.print("\n[bold]1/7 Initializing database...[/bold]")
    init_db(db_path)
    console.print("  Done")

    # 2. Ingest
    console.print("\n[bold]2/7 Ingesting articles from Finnhub...[/bold]")
    client = finnhub.Client(api_key=finnhub_key)
    count = ingest_articles(client, db_path, max_pages=max_pages)
    console.print(f"  Ingested {count} new articles")

    # 3. Embed
    console.print("\n[bold]3/7 Generating embeddings...[/bold]")
    _ensure_analysis_rows(db_path)
    count = embed_articles(db_path, embeddings_path, openrouter_key)
    console.print(f"  Embedded {count} articles")

    # 4. Cluster
    console.print("\n[bold]4/7 Clustering articles...[/bold]")
    n_clusters = cluster_articles(db_path, embeddings_path)
    console.print(f"  Found {n_clusters} clusters")

    # 5. Sentiment
    console.print("\n[bold]5/7 Analyzing sentiment...[/bold]")
    count = analyze_sentiment(db_path, openrouter_key)
    console.print(f"  Scored {count} articles")

    # 6. Label
    console.print("\n[bold]6/7 Labeling narratives...[/bold]")
    n_narratives = label_clusters(db_path, embeddings_path, openrouter_key)
    console.print(f"  Labeled {n_narratives} narratives")

    # 7. Summarize
    console.print("\n[bold]7/7 Generating summaries...[/bold]")
    n_weeks = summarize_narratives(db_path, openrouter_key)
    console.print(f"  Generated {n_weeks} weekly summaries")

    # Report
    console.print("\n" + "=" * 40)
    report = generate_report(db_path)
    console.print(report)


def _ensure_analysis_rows(db_path: str) -> None:
    """Insert analysis rows for any articles missing them."""
    from narratio.db import get_connection

    conn = get_connection(db_path)
    conn.execute(
        """INSERT OR IGNORE INTO article_analysis (article_id)
           SELECT id FROM articles WHERE id NOT IN (SELECT article_id FROM article_analysis)"""
    )
    conn.commit()
    conn.close()


def main():
    """CLI entry point."""
    try:
        cfg = get_config()
    except ValueError as e:
        print(f"Error: {e}")
        print("Copy .env.example to .env and fill in your API keys.")
        sys.exit(1)

    run_pipeline(
        finnhub_key=cfg.finnhub_api_key,
        openrouter_key=cfg.openrouter_api_key,
        db_path=cfg.db_path,
        embeddings_path=cfg.embeddings_path,
    )


if __name__ == "__main__":
    main()
