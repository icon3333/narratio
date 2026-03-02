"""Backfill articles from all sources over a date range."""

import sys
from datetime import datetime, timezone
from rich.console import Console

from narratio.config import get_config
from narratio.db import init_db
from narratio.ingest import ingest_range as nyt_ingest_range
from narratio.ingest_guardian import ingest_range as guardian_ingest_range


def backfill(
    start_year: int = 2025,
    start_month: int = 1,
    end_year: int | None = None,
    end_month: int | None = None,
) -> None:
    console = Console()
    now = datetime.now(timezone.utc)
    if end_year is None:
        end_year = now.year
    if end_month is None:
        end_month = now.month

    try:
        cfg = get_config()
    except ValueError as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)

    init_db(cfg.db_path)

    n_months = (end_year - start_year) * 12 + (end_month - start_month) + 1
    console.print(f"[bold cyan]Narratio Backfill[/bold cyan]")
    console.print(f"Range: {start_year}-{start_month:02d} → {end_year}-{end_month:02d} ({n_months} months)")
    console.print("=" * 50)

    grand_total = 0

    if cfg.nyt_api_key:
        console.print(f"\n[bold]NYT Archive API[/bold] — {n_months} requests, ~12s between each")
        console.print("[dim]  Rate limit: 5 req/min, 500/day. This is well within limits.[/dim]")
        y, m = start_year, start_month
        while (y, m) <= (end_year, end_month):
            with console.status(f"  Fetching NYT {y}-{m:02d}..."):
                from narratio.ingest import ingest_month as nyt_month
                count = nyt_month(cfg.db_path, cfg.nyt_api_key, y, m)
            console.print(f"  {y}-{m:02d}: [green]{count}[/green] articles")
            grand_total += count
            m += 1
            if m > 12:
                m = 1
                y += 1
            if (y, m) <= (end_year, end_month):
                import time
                time.sleep(12)  # respect rate limit
    else:
        console.print("\n[yellow]NYT_API_KEY not set — skipping NYT[/yellow]")

    if cfg.guardian_api_key:
        console.print(f"\n[bold]Guardian Open Platform[/bold] — {n_months} months, paginated")
        console.print("[dim]  Rate limit: 1 req/sec, 5000/day. Auto-paginates within each month.[/dim]")
        y, m = start_year, start_month
        while (y, m) <= (end_year, end_month):
            with console.status(f"  Fetching Guardian {y}-{m:02d}..."):
                from narratio.ingest_guardian import ingest_month as guardian_month
                count = guardian_month(cfg.db_path, cfg.guardian_api_key, y, m)
            console.print(f"  {y}-{m:02d}: [green]{count}[/green] articles")
            grand_total += count
            m += 1
            if m > 12:
                m = 1
                y += 1
    else:
        console.print("\n[yellow]GUARDIAN_API_KEY not set — skipping Guardian[/yellow]")

    console.print("\n" + "=" * 50)
    console.print(f"[bold green]Total ingested: {grand_total} articles[/bold green]")

    # Show DB totals
    from narratio.db import get_connection
    conn = get_connection(cfg.db_path)
    total = conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
    by_source = conn.execute(
        "SELECT source, COUNT(*) as cnt FROM articles GROUP BY source ORDER BY cnt DESC"
    ).fetchall()
    conn.close()

    console.print(f"[bold]Database total: {total} articles[/bold]")
    for row in by_source:
        console.print(f"  {row['source']}: {row['cnt']}")

    # Run analysis pipeline if we have articles
    if total > 0:
        console.print("\n[bold cyan]Running analysis pipeline...[/bold cyan]")
        from narratio.pipeline import run_analysis
        run_analysis(cfg)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Backfill Narratio articles")
    parser.add_argument("--start", default="2025-01", help="Start month (YYYY-MM)")
    parser.add_argument("--end", default=None, help="End month (YYYY-MM), defaults to now")
    args = parser.parse_args()

    sy, sm = int(args.start.split("-")[0]), int(args.start.split("-")[1])
    if args.end:
        ey, em = int(args.end.split("-")[0]), int(args.end.split("-")[1])
    else:
        ey, em = None, None

    backfill(start_year=sy, start_month=sm, end_year=ey, end_month=em)
