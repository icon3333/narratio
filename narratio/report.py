"""CLI report generation using rich."""

from io import StringIO
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from narratio.db import get_connection


def generate_report(db_path: str) -> str:
    buf = StringIO()
    console = Console(file=buf, width=120)
    conn = get_connection(db_path)

    total_articles = conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
    total_narratives = conn.execute("SELECT COUNT(*) FROM narratives").fetchone()[0]
    total_noise = conn.execute("SELECT SUM(total_noise) FROM weekly_totals").fetchone()[0] or 0
    total_clustered = conn.execute("SELECT SUM(total_clustered) FROM weekly_totals").fetchone()[0] or 0

    console.print(Panel(
        f"[bold]Articles:[/bold] {total_articles}  |  "
        f"[bold]Narratives:[/bold] {total_narratives}  |  "
        f"[bold]Clustered:[/bold] {total_clustered}  |  "
        f"[bold]Noise:[/bold] {total_noise}",
        title="[bold cyan]Narratio — Pipeline Report[/bold cyan]",
    ))
    console.print()

    narratives = conn.execute(
        """SELECT n.id, n.label, n.first_seen, n.last_seen, n.status,
                  COUNT(aa.article_id) as article_count
           FROM narratives n
           LEFT JOIN article_analysis aa ON aa.narrative_id = n.id
           GROUP BY n.id
           ORDER BY article_count DESC"""
    ).fetchall()

    table = Table(title="Discovered Narratives", show_lines=True)
    table.add_column("#", style="dim", width=4)
    table.add_column("Label", style="bold", max_width=35)
    table.add_column("Articles", justify="right", width=8)
    table.add_column("First Seen", width=12)
    table.add_column("Last Seen", width=12)
    table.add_column("Status", width=8)

    for i, n in enumerate(narratives, 1):
        status_color = "green" if n["status"] == "active" else "dim"
        table.add_row(
            str(i),
            n["label"],
            str(n["article_count"]),
            n["first_seen"],
            n["last_seen"],
            f"[{status_color}]{n['status']}[/{status_color}]",
        )

    console.print(table)
    console.print()

    for n in narratives[:10]:
        latest_week = conn.execute(
            """SELECT * FROM narrative_weeks
               WHERE narrative_id = ?
               ORDER BY week_start DESC LIMIT 1""",
            (n["id"],),
        ).fetchone()

        if not latest_week:
            continue

        headlines = conn.execute(
            """SELECT headline FROM articles a
               JOIN article_analysis aa ON aa.article_id = a.id
               WHERE aa.narrative_id = ?
               ORDER BY a.published_at DESC LIMIT 5""",
            (n["id"],),
        ).fetchall()

        detail = f"[bold]Share of Attention:[/bold] {latest_week['share_of_attention']}%\n"
        detail += f"[bold]Z-Score:[/bold] {latest_week['z_score'] or 'N/A'}\n"
        detail += f"[bold]Sentiment:[/bold] {latest_week['sentiment_mean'] or 'N/A'}\n"
        detail += f"[bold]Week:[/bold] {latest_week['week_start']}\n"

        if latest_week["summary"]:
            detail += f"\n[italic]{latest_week['summary']}[/italic]\n"

        detail += "\n[bold]Top Headlines:[/bold]\n"
        for h in headlines:
            detail += f"  • {h['headline']}\n"

        console.print(Panel(detail.strip(), title=f"[bold yellow]{n['label']}[/bold yellow]", border_style="yellow"))
        console.print()

    conn.close()
    return buf.getvalue()
