"""Scrape Economist magazine covers via Node.js Puppeteer script."""

import json
import logging
import sqlite3
import subprocess
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

SCRIPT_PATH = str(Path(__file__).parent / "scrape_covers_node.js")


def _run_node_scraper(year: int) -> list[dict]:
    """Run the Node.js Puppeteer scraper and return parsed covers."""
    result = subprocess.run(
        ["node", SCRIPT_PATH, str(year)],
        capture_output=True,
        text=True,
        timeout=60,
    )
    if result.stderr:
        logger.warning("Node scraper stderr: %s", result.stderr.strip())
    if result.returncode != 0:
        logger.error("Node scraper exited with code %d", result.returncode)
        return []
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as e:
        logger.error("Failed to parse scraper output: %s", e)
        return []


def scrape_covers(db_path: str, year: int | None = None) -> int:
    """Scrape Economist covers and store in the database.

    Args:
        db_path: Path to SQLite database.
        year: Specific year to scrape, or None for current year.

    Returns:
        Number of covers found for the requested year(s).
    """
    target_year = year or datetime.now().year
    covers = _run_node_scraper(target_year)

    if not covers:
        return 0

    conn = sqlite3.connect(db_path)
    for cover in covers:
        try:
            conn.execute(
                """INSERT OR IGNORE INTO economist_covers
                   (date, title, image_url, edition_url, year)
                   VALUES (?, ?, ?, ?, ?)""",
                (cover["date"], cover.get("title"), cover["image_url"],
                 cover.get("edition_url"), target_year),
            )
        except sqlite3.Error as e:
            logger.warning("Failed to insert cover %s: %s", cover["date"], e)
    conn.commit()

    count = conn.execute(
        "SELECT COUNT(*) FROM economist_covers WHERE year = ?",
        (target_year,),
    ).fetchone()[0]
    conn.close()

    logger.info("Covers for %d: %d scraped, %d in database", target_year, len(covers), count)
    return count
