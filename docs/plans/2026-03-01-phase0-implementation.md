# Phase 0: Pipeline Proof — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Ingest ~3 months of Finnhub general news, embed, cluster into narratives, label/summarize via LLM, and verify results via CLI report.

**Architecture:** Single Python package (`narratio/`) with one module per pipeline stage. SQLite for structured storage, numpy `.npy` files for embedding vectors. OpenRouter for embeddings, sentiment, labeling, and summarization. CLI orchestrator runs the full pipeline; `rich`-based report verifies results.

**Tech Stack:** Python 3.14, uv, finnhub-python, httpx, hdbscan, numpy, scikit-learn, python-dotenv, rich, pytest

---

### Task 1: Project Scaffolding

**Files:**
- Create: `pyproject.toml`
- Create: `.python-version`
- Create: `.gitignore`
- Create: `.env.example`
- Create: `narratio/__init__.py`
- Create: `narratio/config.py`
- Create: `tests/__init__.py`
- Create: `tests/test_config.py`

**Step 1: Install uv**

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
source ~/.zshrc
```

Verify: `uv --version` prints a version number.

**Step 2: Create pyproject.toml**

```toml
[project]
name = "narratio"
version = "0.1.0"
description = "Financial narrative tracking pipeline"
requires-python = ">=3.12"
dependencies = [
    "finnhub-python>=2.4.20",
    "httpx>=0.27",
    "hdbscan>=0.8.40",
    "numpy>=2.0",
    "scikit-learn>=1.5",
    "python-dotenv>=1.0",
    "rich>=13.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.24",
]

[project.scripts]
narratio = "narratio.pipeline:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

**Step 3: Create .python-version**

```
3.14
```

**Step 4: Create .gitignore**

```
# Python
__pycache__/
*.pyc
.venv/

# Data (large, regenerable)
data/

# Environment
.env

# IDE
.idea/
.vscode/
*.swp
```

**Step 5: Create .env.example**

```
FINNHUB_API_KEY=your_finnhub_api_key_here
OPENROUTER_API_KEY=your_openrouter_api_key_here
```

**Step 6: Create narratio/__init__.py**

```python
"""Narratio — Financial narrative tracking pipeline."""
```

**Step 7: Create tests/__init__.py**

Empty file.

**Step 8: Write the failing test for config**

Create `tests/test_config.py`:

```python
import os

def test_config_loads_from_env(monkeypatch):
    monkeypatch.setenv("FINNHUB_API_KEY", "test-finnhub")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-openrouter")

    from narratio.config import get_config
    cfg = get_config()

    assert cfg.finnhub_api_key == "test-finnhub"
    assert cfg.openrouter_api_key == "test-openrouter"


def test_config_raises_on_missing_keys(monkeypatch):
    monkeypatch.delenv("FINNHUB_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

    from narratio.config import get_config
    import pytest
    with pytest.raises(ValueError, match="FINNHUB_API_KEY"):
        get_config()
```

**Step 9: Run test to verify it fails**

```bash
uv run pytest tests/test_config.py -v
```

Expected: FAIL — `ImportError: cannot import name 'get_config'`

**Step 10: Implement config.py**

Create `narratio/config.py`:

```python
"""Configuration from environment variables."""

import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass(frozen=True)
class Config:
    finnhub_api_key: str
    openrouter_api_key: str
    db_path: str = "data/narratio.db"
    embeddings_path: str = "data/embeddings.npy"


def get_config() -> Config:
    load_dotenv()
    finnhub_key = os.environ.get("FINNHUB_API_KEY")
    openrouter_key = os.environ.get("OPENROUTER_API_KEY")

    if not finnhub_key:
        raise ValueError("FINNHUB_API_KEY environment variable is required")
    if not openrouter_key:
        raise ValueError("OPENROUTER_API_KEY environment variable is required")

    return Config(
        finnhub_api_key=finnhub_key,
        openrouter_api_key=openrouter_key,
    )
```

**Step 11: Run tests to verify they pass**

```bash
uv run pytest tests/test_config.py -v
```

Expected: 2 passed.

**Step 12: Sync dependencies and commit**

```bash
uv sync
git add pyproject.toml .python-version .gitignore .env.example narratio/ tests/
git commit -m "feat: project scaffolding with uv, config, and tests"
```

---

### Task 2: Database Schema & Helpers

**Files:**
- Create: `narratio/db.py`
- Create: `tests/test_db.py`

**Step 1: Write the failing test**

Create `tests/test_db.py`:

```python
import sqlite3
from narratio.db import init_db, get_connection


def test_init_db_creates_tables(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)

    conn = sqlite3.connect(db_path)
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    )
    tables = [row[0] for row in cursor.fetchall()]
    conn.close()

    assert "articles" in tables
    assert "article_analysis" in tables
    assert "narratives" in tables
    assert "narrative_weeks" in tables
    assert "weekly_totals" in tables


def test_init_db_is_idempotent(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    init_db(db_path)  # Should not raise


def test_get_connection(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)
    assert isinstance(conn, sqlite3.Connection)
    conn.close()
```

**Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_db.py -v
```

Expected: FAIL — `ImportError`

**Step 3: Implement db.py**

Create `narratio/db.py`:

```python
"""SQLite database initialization and helpers."""

import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS articles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    finnhub_id INTEGER UNIQUE NOT NULL,
    headline TEXT NOT NULL,
    summary TEXT,
    source TEXT,
    url TEXT,
    published_at INTEGER NOT NULL,
    related_tickers TEXT,
    category TEXT,
    ingested_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS article_analysis (
    article_id INTEGER PRIMARY KEY REFERENCES articles(id),
    embedding_index INTEGER,
    sentiment_score REAL,
    sentiment_label TEXT,
    cluster_id INTEGER,
    narrative_id INTEGER REFERENCES narratives(id)
);

CREATE TABLE IF NOT EXISTS narratives (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    label TEXT NOT NULL,
    first_seen TEXT NOT NULL,
    last_seen TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    centroid_embedding_index INTEGER
);

CREATE TABLE IF NOT EXISTS narrative_weeks (
    narrative_id INTEGER NOT NULL REFERENCES narratives(id),
    week_start TEXT NOT NULL,
    article_count INTEGER NOT NULL DEFAULT 0,
    share_of_attention REAL,
    z_score REAL,
    sentiment_mean REAL,
    summary TEXT,
    top_headline_ids TEXT,
    PRIMARY KEY (narrative_id, week_start)
);

CREATE TABLE IF NOT EXISTS weekly_totals (
    week_start TEXT PRIMARY KEY,
    total_articles INTEGER NOT NULL DEFAULT 0,
    total_clustered INTEGER NOT NULL DEFAULT 0,
    total_noise INTEGER NOT NULL DEFAULT 0
);
"""


def init_db(db_path: str) -> None:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.executescript(SCHEMA)
    conn.close()


def get_connection(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn
```

**Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_db.py -v
```

Expected: 3 passed.

**Step 5: Commit**

```bash
git add narratio/db.py tests/test_db.py
git commit -m "feat: SQLite schema and db helpers"
```

---

### Task 3: Finnhub Ingestion

**Files:**
- Create: `narratio/ingest.py`
- Create: `tests/test_ingest.py`

**Step 1: Write the failing test**

Create `tests/test_ingest.py`:

```python
import sqlite3
from unittest.mock import MagicMock
from narratio.db import init_db, get_connection
from narratio.ingest import parse_article, ingest_articles


def _make_finnhub_article(id=1, headline="Test headline", summary="Test summary"):
    return {
        "id": id,
        "headline": headline,
        "summary": summary,
        "source": "reuters",
        "url": "https://example.com/1",
        "datetime": 1700000000,
        "related": "AAPL,MSFT",
        "category": "general",
    }


def test_parse_article():
    raw = _make_finnhub_article()
    parsed = parse_article(raw)
    assert parsed["finnhub_id"] == 1
    assert parsed["headline"] == "Test headline"
    assert parsed["related_tickers"] == "AAPL,MSFT"


def test_ingest_articles_inserts_rows(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)

    articles = [_make_finnhub_article(id=i, headline=f"Headline {i}") for i in range(5)]

    mock_client = MagicMock()
    mock_client.general_news.return_value = articles

    count = ingest_articles(mock_client, db_path, category="general", max_pages=1)
    assert count == 5

    conn = get_connection(db_path)
    rows = conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
    conn.close()
    assert rows == 5


def test_ingest_articles_skips_duplicates(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)

    articles = [_make_finnhub_article(id=1)]
    mock_client = MagicMock()
    mock_client.general_news.return_value = articles

    ingest_articles(mock_client, db_path, category="general", max_pages=1)
    ingest_articles(mock_client, db_path, category="general", max_pages=1)

    conn = get_connection(db_path)
    rows = conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
    conn.close()
    assert rows == 1
```

**Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_ingest.py -v
```

Expected: FAIL — `ImportError`

**Step 3: Implement ingest.py**

Create `narratio/ingest.py`:

```python
"""Finnhub news ingestion."""

import time
from narratio.db import get_connection


def parse_article(raw: dict) -> dict:
    return {
        "finnhub_id": raw["id"],
        "headline": raw.get("headline", ""),
        "summary": raw.get("summary", ""),
        "source": raw.get("source", ""),
        "url": raw.get("url", ""),
        "published_at": raw.get("datetime", 0),
        "related_tickers": raw.get("related", ""),
        "category": raw.get("category", ""),
    }


def ingest_articles(
    client,
    db_path: str,
    category: str = "general",
    max_pages: int = 100,
    delay: float = 1.0,
) -> int:
    conn = get_connection(db_path)
    total_inserted = 0
    min_id = 0

    for page in range(max_pages):
        articles = client.general_news(category, min_id=min_id)
        if not articles:
            break

        for raw in articles:
            parsed = parse_article(raw)
            try:
                conn.execute(
                    """INSERT INTO articles
                       (finnhub_id, headline, summary, source, url,
                        published_at, related_tickers, category)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        parsed["finnhub_id"],
                        parsed["headline"],
                        parsed["summary"],
                        parsed["source"],
                        parsed["url"],
                        parsed["published_at"],
                        parsed["related_tickers"],
                        parsed["category"],
                    ),
                )
                total_inserted += 1
            except Exception:
                pass  # Skip duplicates (UNIQUE constraint on finnhub_id)

        conn.commit()

        # Paginate: use the minimum id from this batch
        batch_ids = [a["id"] for a in articles]
        if not batch_ids:
            break
        min_id = min(batch_ids)

        # Stop if we got fewer articles than expected (last page)
        if len(articles) < 100:
            break

        if delay > 0 and page < max_pages - 1:
            time.sleep(delay)

    conn.close()
    return total_inserted
```

**Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_ingest.py -v
```

Expected: 3 passed.

**Step 5: Commit**

```bash
git add narratio/ingest.py tests/test_ingest.py
git commit -m "feat: Finnhub news ingestion with pagination and dedup"
```

---

### Task 4: Embedding via OpenRouter

**Files:**
- Create: `narratio/embed.py`
- Create: `tests/test_embed.py`

**Step 1: Write the failing test**

Create `tests/test_embed.py`:

```python
import json
import numpy as np
from unittest.mock import AsyncMock, patch
from narratio.db import init_db, get_connection
from narratio.embed import embed_articles, _build_embed_request


def test_build_embed_request():
    texts = ["headline one", "headline two"]
    req = _build_embed_request(texts)
    assert req["model"] == "openai/text-embedding-3-small"
    assert req["input"] == texts


def test_embed_articles_stores_embeddings(tmp_path):
    db_path = str(tmp_path / "test.db")
    embeddings_path = str(tmp_path / "embeddings.npy")
    init_db(db_path)

    # Insert test articles
    conn = get_connection(db_path)
    for i in range(3):
        conn.execute(
            """INSERT INTO articles (finnhub_id, headline, summary, source, url, published_at, category)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (i, f"Headline {i}", f"Summary {i}", "test", "http://test.com", 1700000000 + i, "general"),
        )
        conn.execute(
            "INSERT INTO article_analysis (article_id) VALUES (?)",
            (i + 1,),
        )
    conn.commit()
    conn.close()

    # Mock the OpenRouter response
    fake_embeddings = np.random.rand(3, 1536).tolist()
    mock_response = {
        "data": [{"embedding": fake_embeddings[i], "index": i} for i in range(3)]
    }

    with patch("narratio.embed._call_openrouter_embed") as mock_call:
        mock_call.return_value = mock_response
        count = embed_articles(db_path, embeddings_path, "fake-key", batch_size=10)

    assert count == 3

    # Verify numpy file
    emb = np.load(embeddings_path)
    assert emb.shape == (3, 1536)

    # Verify embedding_index stored
    conn = get_connection(db_path)
    rows = conn.execute("SELECT embedding_index FROM article_analysis ORDER BY article_id").fetchall()
    conn.close()
    indices = [r[0] for r in rows]
    assert indices == [0, 1, 2]
```

**Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_embed.py -v
```

Expected: FAIL — `ImportError`

**Step 3: Implement embed.py**

Create `narratio/embed.py`:

```python
"""Embed article headlines via OpenRouter embeddings API."""

import numpy as np
import httpx
from pathlib import Path
from narratio.db import get_connection

EMBED_MODEL = "openai/text-embedding-3-small"
OPENROUTER_EMBED_URL = "https://openrouter.ai/api/v1/embeddings"


def _build_embed_request(texts: list[str]) -> dict:
    return {
        "model": EMBED_MODEL,
        "input": texts,
    }


def _call_openrouter_embed(texts: list[str], api_key: str) -> dict:
    req = _build_embed_request(texts)
    resp = httpx.post(
        OPENROUTER_EMBED_URL,
        json=req,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()


def embed_articles(
    db_path: str,
    embeddings_path: str,
    api_key: str,
    batch_size: int = 100,
) -> int:
    conn = get_connection(db_path)

    # Get articles that need embedding (embedding_index is NULL)
    rows = conn.execute(
        """SELECT a.id, a.headline, a.summary
           FROM articles a
           JOIN article_analysis aa ON aa.article_id = a.id
           WHERE aa.embedding_index IS NULL
           ORDER BY a.id"""
    ).fetchall()

    if not rows:
        conn.close()
        return 0

    # Load existing embeddings if any
    emb_path = Path(embeddings_path)
    if emb_path.exists():
        existing = np.load(str(emb_path))
        all_embeddings = list(existing)
    else:
        emb_path.parent.mkdir(parents=True, exist_ok=True)
        all_embeddings = []

    total = 0
    for i in range(0, len(rows), batch_size):
        batch = rows[i : i + batch_size]
        texts = [f"{r['headline']}. {r['summary']}" for r in batch]

        result = _call_openrouter_embed(texts, api_key)

        # Sort by index to maintain order
        sorted_data = sorted(result["data"], key=lambda x: x["index"])

        for j, item in enumerate(sorted_data):
            emb_index = len(all_embeddings)
            all_embeddings.append(item["embedding"])
            article_id = batch[j]["id"]
            conn.execute(
                "UPDATE article_analysis SET embedding_index = ? WHERE article_id = ?",
                (emb_index, article_id),
            )
            total += 1

        conn.commit()

    # Save all embeddings
    np.save(str(emb_path), np.array(all_embeddings, dtype=np.float32))
    conn.close()
    return total
```

**Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_embed.py -v
```

Expected: 1 passed.

**Step 5: Commit**

```bash
git add narratio/embed.py tests/test_embed.py
git commit -m "feat: OpenRouter embedding with numpy storage"
```

---

### Task 5: HDBSCAN Clustering

**Files:**
- Create: `narratio/cluster.py`
- Create: `tests/test_cluster.py`

**Step 1: Write the failing test**

Create `tests/test_cluster.py`:

```python
import numpy as np
from narratio.db import init_db, get_connection
from narratio.cluster import cluster_articles


def _seed_db_with_embeddings(db_path, embeddings_path, n=60):
    """Create n articles with embeddings forming 2 clusters + noise."""
    init_db(db_path)
    conn = get_connection(db_path)

    # Create 2 tight clusters of 25 each + 10 noise
    rng = np.random.default_rng(42)
    embeddings = []

    for i in range(n):
        conn.execute(
            """INSERT INTO articles (finnhub_id, headline, summary, source, url, published_at, category)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (i, f"Headline {i}", f"Summary {i}", "test", "http://test.com", 1700000000 + i, "general"),
        )
        conn.execute(
            "INSERT INTO article_analysis (article_id, embedding_index) VALUES (?, ?)",
            (i + 1, i),
        )

        # Cluster 1: centered around [1, 0, 0, ...]
        if i < 25:
            emb = np.zeros(1536, dtype=np.float32)
            emb[0] = 1.0
            emb += rng.normal(0, 0.05, 1536).astype(np.float32)
        # Cluster 2: centered around [0, 1, 0, ...]
        elif i < 50:
            emb = np.zeros(1536, dtype=np.float32)
            emb[1] = 1.0
            emb += rng.normal(0, 0.05, 1536).astype(np.float32)
        # Noise: random
        else:
            emb = rng.normal(0, 1, 1536).astype(np.float32)

        embeddings.append(emb)

    conn.commit()
    conn.close()

    np.save(embeddings_path, np.array(embeddings, dtype=np.float32))


def test_cluster_articles_assigns_cluster_ids(tmp_path):
    db_path = str(tmp_path / "test.db")
    emb_path = str(tmp_path / "embeddings.npy")
    _seed_db_with_embeddings(db_path, emb_path, n=60)

    n_clusters = cluster_articles(db_path, emb_path, min_cluster_size=10)

    assert n_clusters >= 2

    conn = get_connection(db_path)
    rows = conn.execute(
        "SELECT cluster_id FROM article_analysis WHERE cluster_id IS NOT NULL"
    ).fetchall()
    conn.close()

    assert len(rows) >= 40  # At least the 2 tight clusters
```

**Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_cluster.py -v
```

Expected: FAIL — `ImportError`

**Step 3: Implement cluster.py**

Create `narratio/cluster.py`:

```python
"""HDBSCAN clustering of article embeddings."""

import numpy as np
import hdbscan
from sklearn.preprocessing import normalize
from narratio.db import get_connection


def cluster_articles(
    db_path: str,
    embeddings_path: str,
    min_cluster_size: int = 15,
) -> int:
    conn = get_connection(db_path)

    # Get articles that have embeddings
    rows = conn.execute(
        """SELECT article_id, embedding_index FROM article_analysis
           WHERE embedding_index IS NOT NULL
           ORDER BY article_id"""
    ).fetchall()

    if not rows:
        conn.close()
        return 0

    embeddings = np.load(embeddings_path)
    indices = [r["embedding_index"] for r in rows]
    article_ids = [r["article_id"] for r in rows]
    vectors = normalize(embeddings[indices])

    clusterer = hdbscan.HDBSCAN(
        min_cluster_size=min_cluster_size,
        metric="euclidean",  # on L2-normalized vectors, euclidean ~ cosine
        cluster_selection_method="eom",
    )
    labels = clusterer.fit_predict(vectors)

    for article_id, label in zip(article_ids, labels):
        cluster_id = int(label) if label >= 0 else None
        conn.execute(
            "UPDATE article_analysis SET cluster_id = ? WHERE article_id = ?",
            (cluster_id, article_id),
        )

    conn.commit()
    conn.close()

    n_clusters = len(set(labels)) - (1 if -1 in labels else 0)
    return n_clusters
```

**Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_cluster.py -v
```

Expected: 1 passed.

**Step 5: Commit**

```bash
git add narratio/cluster.py tests/test_cluster.py
git commit -m "feat: HDBSCAN clustering on normalized embeddings"
```

---

### Task 6: Sentiment Analysis via OpenRouter

**Files:**
- Create: `narratio/sentiment.py`
- Create: `tests/test_sentiment.py`

**Step 1: Write the failing test**

Create `tests/test_sentiment.py`:

```python
from unittest.mock import patch
from narratio.db import init_db, get_connection
from narratio.sentiment import analyze_sentiment, _parse_sentiment_response


def test_parse_sentiment_response():
    raw = '{"score": 0.6, "label": "bullish"}'
    score, label = _parse_sentiment_response(raw)
    assert score == 0.6
    assert label == "bullish"


def test_parse_sentiment_response_handles_plain_text():
    raw = "bullish 0.7"
    score, label = _parse_sentiment_response(raw)
    assert label in ("bullish", "bearish", "neutral")
    assert -1.0 <= score <= 1.0


def test_analyze_sentiment_updates_db(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)

    for i in range(3):
        conn.execute(
            """INSERT INTO articles (finnhub_id, headline, summary, source, url, published_at, category)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (i, f"Headline {i}", f"Summary {i}", "test", "http://test.com", 1700000000, "general"),
        )
        conn.execute(
            "INSERT INTO article_analysis (article_id) VALUES (?)",
            (i + 1,),
        )
    conn.commit()
    conn.close()

    fake_response = {
        "choices": [{"message": {"content": '{"score": 0.5, "label": "bullish"}'}}]
    }

    with patch("narratio.sentiment._call_openrouter_chat") as mock_call:
        mock_call.return_value = fake_response
        count = analyze_sentiment(db_path, "fake-key", batch_size=10)

    assert count == 3

    conn = get_connection(db_path)
    rows = conn.execute("SELECT sentiment_score, sentiment_label FROM article_analysis").fetchall()
    conn.close()

    for r in rows:
        assert r["sentiment_score"] == 0.5
        assert r["sentiment_label"] == "bullish"
```

**Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_sentiment.py -v
```

Expected: FAIL — `ImportError`

**Step 3: Implement sentiment.py**

Create `narratio/sentiment.py`:

```python
"""Sentiment analysis via OpenRouter (Gemini Flash)."""

import json
import re
import httpx
from narratio.db import get_connection

SENTIMENT_MODEL = "google/gemini-2.0-flash-001"
OPENROUTER_CHAT_URL = "https://openrouter.ai/api/v1/chat/completions"

SENTIMENT_PROMPT = """Classify this financial headline's sentiment as bearish, neutral, or bullish.
Return ONLY a JSON object: {"score": <float from -1.0 to 1.0>, "label": "<bearish|neutral|bullish>"}

Headline: {headline}
Summary: {summary}"""


def _call_openrouter_chat(messages: list[dict], api_key: str, model: str = SENTIMENT_MODEL) -> dict:
    resp = httpx.post(
        OPENROUTER_CHAT_URL,
        json={"model": model, "messages": messages, "temperature": 0},
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()


def _parse_sentiment_response(raw: str) -> tuple[float, str]:
    try:
        data = json.loads(raw.strip())
        return float(data["score"]), data["label"]
    except (json.JSONDecodeError, KeyError):
        # Fallback: extract from plain text
        raw_lower = raw.lower()
        if "bullish" in raw_lower:
            label = "bullish"
        elif "bearish" in raw_lower:
            label = "bearish"
        else:
            label = "neutral"

        numbers = re.findall(r"-?\d+\.?\d*", raw)
        score = float(numbers[0]) if numbers else (0.5 if label == "bullish" else -0.5 if label == "bearish" else 0.0)
        score = max(-1.0, min(1.0, score))
        return score, label


def analyze_sentiment(
    db_path: str,
    api_key: str,
    batch_size: int = 20,
) -> int:
    conn = get_connection(db_path)

    rows = conn.execute(
        """SELECT a.id, a.headline, a.summary
           FROM articles a
           JOIN article_analysis aa ON aa.article_id = a.id
           WHERE aa.sentiment_score IS NULL
           ORDER BY a.id"""
    ).fetchall()

    if not rows:
        conn.close()
        return 0

    total = 0
    for i in range(0, len(rows), batch_size):
        batch = rows[i : i + batch_size]

        # Build batch prompt: multiple headlines in one call
        headlines_text = "\n---\n".join(
            f"[{j}] Headline: {r['headline']}\nSummary: {r['summary']}"
            for j, r in enumerate(batch)
        )

        messages = [
            {
                "role": "user",
                "content": f"""Classify each headline's sentiment. Return a JSON array of objects, one per headline.
Each object: {{"index": <int>, "score": <float -1.0 to 1.0>, "label": "<bearish|neutral|bullish>"}}

{headlines_text}""",
            }
        ]

        result = _call_openrouter_chat(messages, api_key)
        content = result["choices"][0]["message"]["content"]

        try:
            sentiments = json.loads(content.strip().removeprefix("```json").removesuffix("```").strip())
            if isinstance(sentiments, dict):
                sentiments = [sentiments]
        except json.JSONDecodeError:
            # Single-article fallback
            score, label = _parse_sentiment_response(content)
            sentiments = [{"index": j, "score": score, "label": label} for j in range(len(batch))]

        for item in sentiments:
            idx = item.get("index", 0)
            if idx < len(batch):
                score = max(-1.0, min(1.0, float(item.get("score", 0))))
                label = item.get("label", "neutral")
                conn.execute(
                    "UPDATE article_analysis SET sentiment_score = ?, sentiment_label = ? WHERE article_id = ?",
                    (score, label, batch[idx]["id"]),
                )
                total += 1

        conn.commit()

    conn.close()
    return total
```

**Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_sentiment.py -v
```

Expected: 3 passed.

**Step 5: Commit**

```bash
git add narratio/sentiment.py tests/test_sentiment.py
git commit -m "feat: sentiment analysis via OpenRouter Gemini Flash"
```

---

### Task 7: Narrative Labeling via OpenRouter

**Files:**
- Create: `narratio/label.py`
- Create: `tests/test_label.py`

**Step 1: Write the failing test**

Create `tests/test_label.py`:

```python
import numpy as np
from unittest.mock import patch
from narratio.db import init_db, get_connection
from narratio.label import label_clusters, _build_label_prompt


def test_build_label_prompt():
    headlines = ["Fed cuts rates", "Rate cut expectations rise", "Markets rally on rate hopes"]
    prompt = _build_label_prompt(headlines)
    assert "Fed cuts rates" in prompt
    assert "3-6 word" in prompt.lower() or "short" in prompt.lower()


def test_label_clusters_creates_narratives(tmp_path):
    db_path = str(tmp_path / "test.db")
    emb_path = str(tmp_path / "embeddings.npy")
    init_db(db_path)
    conn = get_connection(db_path)

    # Create 20 articles in cluster 0
    embeddings = []
    for i in range(20):
        conn.execute(
            """INSERT INTO articles (finnhub_id, headline, summary, source, url, published_at, category)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (i, f"Fed rate cut headline {i}", "summary", "test", "http://test.com", 1700000000, "general"),
        )
        conn.execute(
            "INSERT INTO article_analysis (article_id, embedding_index, cluster_id) VALUES (?, ?, ?)",
            (i + 1, i, 0),
        )
        emb = np.random.rand(1536).astype(np.float32)
        embeddings.append(emb)

    conn.commit()
    conn.close()
    np.save(emb_path, np.array(embeddings))

    fake_response = {
        "choices": [{"message": {"content": "Fed Rate Cut Expectations"}}]
    }

    with patch("narratio.label._call_openrouter_chat") as mock_call:
        mock_call.return_value = fake_response
        n = label_clusters(db_path, emb_path, "fake-key")

    assert n == 1

    conn = get_connection(db_path)
    narrative = conn.execute("SELECT label FROM narratives").fetchone()
    conn.close()
    assert narrative is not None
    assert "Fed" in narrative["label"] or "Rate" in narrative["label"]
```

**Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_label.py -v
```

Expected: FAIL — `ImportError`

**Step 3: Implement label.py**

Create `narratio/label.py`:

```python
"""Narrative labeling via OpenRouter (Gemini Flash)."""

import json
import numpy as np
import httpx
from datetime import datetime, timezone
from narratio.db import get_connection

LABEL_MODEL = "google/gemini-2.0-flash-001"
OPENROUTER_CHAT_URL = "https://openrouter.ai/api/v1/chat/completions"


def _call_openrouter_chat(messages: list[dict], api_key: str, model: str = LABEL_MODEL) -> dict:
    resp = httpx.post(
        OPENROUTER_CHAT_URL,
        json={"model": model, "messages": messages, "temperature": 0},
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()


def _build_label_prompt(headlines: list[str]) -> str:
    headlines_text = "\n".join(f"- {h}" for h in headlines[:10])
    return f"""These headlines belong to the same financial news cluster. Generate a short, descriptive label (3-6 words) that captures the common theme.

Headlines:
{headlines_text}

Return ONLY the label, nothing else. Example: "Fed Rate Cut Expectations" or "China Property Crisis"."""


def label_clusters(
    db_path: str,
    embeddings_path: str,
    api_key: str,
) -> int:
    conn = get_connection(db_path)
    embeddings = np.load(embeddings_path)

    # Get distinct cluster IDs (excluding noise = NULL)
    clusters = conn.execute(
        "SELECT DISTINCT cluster_id FROM article_analysis WHERE cluster_id IS NOT NULL ORDER BY cluster_id"
    ).fetchall()

    n_labeled = 0

    for row in clusters:
        cluster_id = row["cluster_id"]

        # Get top headlines for this cluster (by article_id, as proxy for representativeness)
        articles = conn.execute(
            """SELECT a.id, a.headline, a.published_at, aa.embedding_index
               FROM articles a
               JOIN article_analysis aa ON aa.article_id = a.id
               WHERE aa.cluster_id = ?
               ORDER BY a.published_at DESC
               LIMIT 10""",
            (cluster_id,),
        ).fetchall()

        if not articles:
            continue

        # Generate label
        headlines = [a["headline"] for a in articles]
        messages = [{"role": "user", "content": _build_label_prompt(headlines)}]
        result = _call_openrouter_chat(messages, api_key)
        label = result["choices"][0]["message"]["content"].strip().strip('"').strip("'")

        # Compute centroid
        emb_indices = [a["embedding_index"] for a in articles if a["embedding_index"] is not None]
        all_cluster_articles = conn.execute(
            "SELECT embedding_index FROM article_analysis WHERE cluster_id = ? AND embedding_index IS NOT NULL",
            (cluster_id,),
        ).fetchall()
        all_indices = [r["embedding_index"] for r in all_cluster_articles]
        centroid_index = all_indices[0]  # placeholder, centroid stored separately

        # Get date range
        dates = conn.execute(
            """SELECT MIN(a.published_at) as first, MAX(a.published_at) as last
               FROM articles a JOIN article_analysis aa ON aa.article_id = a.id
               WHERE aa.cluster_id = ?""",
            (cluster_id,),
        ).fetchone()

        first_seen = datetime.fromtimestamp(dates["first"], tz=timezone.utc).strftime("%Y-%m-%d")
        last_seen = datetime.fromtimestamp(dates["last"], tz=timezone.utc).strftime("%Y-%m-%d")

        # Insert narrative
        cursor = conn.execute(
            """INSERT INTO narratives (label, first_seen, last_seen, status, centroid_embedding_index)
               VALUES (?, ?, ?, 'active', ?)""",
            (label, first_seen, last_seen, centroid_index),
        )
        narrative_id = cursor.lastrowid

        # Link articles to narrative
        conn.execute(
            "UPDATE article_analysis SET narrative_id = ? WHERE cluster_id = ?",
            (narrative_id, cluster_id),
        )

        conn.commit()
        n_labeled += 1

    conn.close()
    return n_labeled
```

**Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_label.py -v
```

Expected: 2 passed.

**Step 5: Commit**

```bash
git add narratio/label.py tests/test_label.py
git commit -m "feat: narrative labeling via OpenRouter Gemini Flash"
```

---

### Task 8: Weekly Summarization via OpenRouter

**Files:**
- Create: `narratio/summarize.py`
- Create: `tests/test_summarize.py`

**Step 1: Write the failing test**

Create `tests/test_summarize.py`:

```python
from unittest.mock import patch
from narratio.db import init_db, get_connection
from narratio.summarize import summarize_narratives


def test_summarize_narratives_creates_weekly_records(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)

    # Insert a narrative
    conn.execute(
        "INSERT INTO narratives (id, label, first_seen, last_seen, status) VALUES (1, 'Fed Rate Cuts', '2025-12-01', '2025-12-15', 'active')"
    )

    # Insert articles across 2 weeks
    for i in range(10):
        week_ts = 1733011200 if i < 5 else 1733616000  # Dec 1 and Dec 8 2024
        conn.execute(
            """INSERT INTO articles (finnhub_id, headline, summary, source, url, published_at, category)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (i, f"Fed rate headline {i}", f"Summary about rates {i}", "test", "http://test.com", week_ts, "general"),
        )
        conn.execute(
            "INSERT INTO article_analysis (article_id, narrative_id, sentiment_score) VALUES (?, 1, 0.3)",
            (i + 1,),
        )

    conn.commit()
    conn.close()

    fake_response = {
        "choices": [{"message": {"content": "Markets increasingly expect rate cuts as economic data softens."}}]
    }

    with patch("narratio.summarize._call_openrouter_chat") as mock_call:
        mock_call.return_value = fake_response
        count = summarize_narratives(db_path, "fake-key")

    assert count >= 1

    conn = get_connection(db_path)
    weeks = conn.execute("SELECT * FROM narrative_weeks WHERE narrative_id = 1").fetchall()
    totals = conn.execute("SELECT * FROM weekly_totals").fetchall()
    conn.close()

    assert len(weeks) >= 1
    assert len(totals) >= 1
    assert weeks[0]["summary"] is not None
```

**Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_summarize.py -v
```

Expected: FAIL — `ImportError`

**Step 3: Implement summarize.py**

Create `narratio/summarize.py`:

```python
"""Weekly narrative summarization and analytics computation."""

import json
from datetime import datetime, timezone, timedelta
import httpx
import numpy as np
from narratio.db import get_connection

SUMMARY_MODEL = "anthropic/claude-sonnet-4"
OPENROUTER_CHAT_URL = "https://openrouter.ai/api/v1/chat/completions"


def _call_openrouter_chat(messages: list[dict], api_key: str, model: str = SUMMARY_MODEL) -> dict:
    resp = httpx.post(
        OPENROUTER_CHAT_URL,
        json={"model": model, "messages": messages, "temperature": 0.3},
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        timeout=120,
    )
    resp.raise_for_status()
    return resp.json()


def _week_start(timestamp: int) -> str:
    dt = datetime.fromtimestamp(timestamp, tz=timezone.utc)
    monday = dt - timedelta(days=dt.weekday())
    return monday.strftime("%Y-%m-%d")


def summarize_narratives(db_path: str, api_key: str) -> int:
    conn = get_connection(db_path)

    narratives = conn.execute("SELECT id, label FROM narratives").fetchall()
    if not narratives:
        conn.close()
        return 0

    # Group articles by narrative and week
    all_articles = conn.execute(
        """SELECT a.id, a.headline, a.summary, a.published_at,
                  aa.narrative_id, aa.sentiment_score
           FROM articles a
           JOIN article_analysis aa ON aa.article_id = a.id
           WHERE aa.narrative_id IS NOT NULL
           ORDER BY a.published_at"""
    ).fetchall()

    # Build weekly buckets: {narrative_id: {week_start: [articles]}}
    buckets: dict[int, dict[str, list]] = {}
    weekly_article_counts: dict[str, int] = {}
    weekly_clustered_counts: dict[str, int] = {}

    for a in all_articles:
        nid = a["narrative_id"]
        ws = _week_start(a["published_at"])
        buckets.setdefault(nid, {}).setdefault(ws, []).append(a)
        weekly_clustered_counts[ws] = weekly_clustered_counts.get(ws, 0) + 1

    # Count total articles per week (including noise)
    total_articles = conn.execute(
        "SELECT published_at FROM articles ORDER BY published_at"
    ).fetchall()
    for a in total_articles:
        ws = _week_start(a["published_at"])
        weekly_article_counts[ws] = weekly_article_counts.get(ws, 0) + 1

    # Compute noise per week
    for ws in weekly_article_counts:
        noise = weekly_article_counts[ws] - weekly_clustered_counts.get(ws, 0)
        conn.execute(
            """INSERT OR REPLACE INTO weekly_totals (week_start, total_articles, total_clustered, total_noise)
               VALUES (?, ?, ?, ?)""",
            (ws, weekly_article_counts[ws], weekly_clustered_counts.get(ws, 0), noise),
        )
    conn.commit()

    # For each narrative, compute weekly stats and generate summaries
    total_weeks_processed = 0

    for narrative in narratives:
        nid = narrative["id"]
        label = narrative["label"]
        weeks_data = buckets.get(nid, {})

        for ws, articles in sorted(weeks_data.items()):
            article_count = len(articles)
            total_week = weekly_article_counts.get(ws, 1)
            share = (article_count / total_week) * 100

            sentiments = [a["sentiment_score"] for a in articles if a["sentiment_score"] is not None]
            sentiment_mean = sum(sentiments) / len(sentiments) if sentiments else 0.0

            headlines = [a["headline"] for a in articles[:10]]
            top_ids = json.dumps([a["id"] for a in articles[:5]])

            # Generate summary
            headlines_text = "\n".join(f"- {h}" for h in headlines)
            messages = [
                {
                    "role": "user",
                    "content": f"""Summarize this week's development for the "{label}" narrative in 1-2 sentences.
Focus on what changed or what's new this week.

Headlines from week of {ws}:
{headlines_text}""",
                }
            ]

            result = _call_openrouter_chat(messages, api_key)
            summary = result["choices"][0]["message"]["content"].strip()

            conn.execute(
                """INSERT OR REPLACE INTO narrative_weeks
                   (narrative_id, week_start, article_count, share_of_attention,
                    sentiment_mean, summary, top_headline_ids)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (nid, ws, article_count, round(share, 2), round(sentiment_mean, 3), summary, top_ids),
            )
            total_weeks_processed += 1

        conn.commit()

    # Compute z-scores across full history
    _compute_z_scores(conn)
    conn.commit()
    conn.close()
    return total_weeks_processed


def _compute_z_scores(conn, window: int = 8):
    """Compute z-scores for share_of_attention across full history."""
    narratives = conn.execute("SELECT DISTINCT narrative_id FROM narrative_weeks").fetchall()

    for row in narratives:
        nid = row["narrative_id"]
        weeks = conn.execute(
            "SELECT week_start, share_of_attention FROM narrative_weeks WHERE narrative_id = ? ORDER BY week_start",
            (nid,),
        ).fetchall()

        shares = [w["share_of_attention"] for w in weeks]
        week_starts = [w["week_start"] for w in weeks]

        for i, (ws, share) in enumerate(zip(week_starts, shares)):
            start = max(0, i - window)
            window_shares = shares[start:i] if i > 0 else shares[:1]

            if len(window_shares) < 2:
                z = 0.0
            else:
                mean = sum(window_shares) / len(window_shares)
                std = (sum((s - mean) ** 2 for s in window_shares) / len(window_shares)) ** 0.5
                z = (share - mean) / std if std > 0 else 0.0

            conn.execute(
                "UPDATE narrative_weeks SET z_score = ? WHERE narrative_id = ? AND week_start = ?",
                (round(z, 3), nid, ws),
            )
```

**Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_summarize.py -v
```

Expected: 1 passed.

**Step 5: Commit**

```bash
git add narratio/summarize.py tests/test_summarize.py
git commit -m "feat: weekly summarization, share-of-attention, and z-scores"
```

---

### Task 9: CLI Report

**Files:**
- Create: `narratio/report.py`
- Create: `tests/test_report.py`

**Step 1: Write the failing test**

Create `tests/test_report.py`:

```python
from narratio.db import init_db, get_connection
from narratio.report import generate_report


def test_generate_report_returns_string(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)

    conn.execute("INSERT INTO narratives (id, label, first_seen, last_seen, status) VALUES (1, 'Fed Rate Cuts', '2025-12-01', '2025-12-15', 'active')")
    conn.execute(
        """INSERT INTO narrative_weeks (narrative_id, week_start, article_count, share_of_attention, z_score, sentiment_mean, summary)
           VALUES (1, '2025-12-01', 25, 15.5, 1.2, 0.3, 'Markets expect rate cuts.')"""
    )
    conn.execute(
        """INSERT INTO weekly_totals (week_start, total_articles, total_clustered, total_noise)
           VALUES ('2025-12-01', 161, 130, 31)"""
    )

    # Add some articles for headline display
    for i in range(5):
        conn.execute(
            """INSERT INTO articles (finnhub_id, headline, summary, source, url, published_at, category)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (i, f"Fed rate headline {i}", "summary", "test", "http://test.com", 1733011200, "general"),
        )
        conn.execute(
            "INSERT INTO article_analysis (article_id, narrative_id) VALUES (?, 1)",
            (i + 1,),
        )
    conn.commit()
    conn.close()

    output = generate_report(db_path)
    assert "Fed Rate Cuts" in output
    assert "15.5" in output or "15.5%" in output
```

**Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_report.py -v
```

Expected: FAIL — `ImportError`

**Step 3: Implement report.py**

Create `narratio/report.py`:

```python
"""CLI report generation using rich."""

from io import StringIO
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from narratio.db import get_connection


def generate_report(db_path: str) -> str:
    buf = StringIO()
    console = Console(file=buf, width=120)
    conn = get_connection(db_path)

    # Overall stats
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

    # Narrative table
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

    # Detail per narrative: latest week stats + top headlines
    for n in narratives[:10]:  # Top 10
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
```

**Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_report.py -v
```

Expected: 1 passed.

**Step 5: Commit**

```bash
git add narratio/report.py tests/test_report.py
git commit -m "feat: CLI report with rich tables and narrative details"
```

---

### Task 10: Pipeline Orchestrator

**Files:**
- Create: `narratio/pipeline.py`
- Create: `tests/test_pipeline.py`

**Step 1: Write the failing test**

Create `tests/test_pipeline.py`:

```python
from unittest.mock import patch, MagicMock
from narratio.pipeline import run_pipeline


def test_run_pipeline_calls_stages_in_order(tmp_path):
    db_path = str(tmp_path / "test.db")
    emb_path = str(tmp_path / "embeddings.npy")

    call_order = []

    with (
        patch("narratio.pipeline.init_db") as mock_init,
        patch("narratio.pipeline.ingest_articles", return_value=100) as mock_ingest,
        patch("narratio.pipeline.embed_articles", return_value=100) as mock_embed,
        patch("narratio.pipeline.cluster_articles", return_value=5) as mock_cluster,
        patch("narratio.pipeline.analyze_sentiment", return_value=100) as mock_sentiment,
        patch("narratio.pipeline.label_clusters", return_value=5) as mock_label,
        patch("narratio.pipeline.summarize_narratives", return_value=10) as mock_summarize,
        patch("narratio.pipeline.generate_report", return_value="report output") as mock_report,
        patch("narratio.pipeline.finnhub") as mock_finnhub,
    ):
        mock_init.side_effect = lambda *a: call_order.append("init_db")
        mock_ingest.side_effect = lambda *a, **kw: (call_order.append("ingest"), 100)[1]
        mock_embed.side_effect = lambda *a, **kw: (call_order.append("embed"), 100)[1]
        mock_cluster.side_effect = lambda *a, **kw: (call_order.append("cluster"), 5)[1]
        mock_sentiment.side_effect = lambda *a, **kw: (call_order.append("sentiment"), 100)[1]
        mock_label.side_effect = lambda *a, **kw: (call_order.append("label"), 5)[1]
        mock_summarize.side_effect = lambda *a, **kw: (call_order.append("summarize"), 10)[1]
        mock_report.side_effect = lambda *a: (call_order.append("report"), "output")[1]

        run_pipeline(
            finnhub_key="test-key",
            openrouter_key="test-key",
            db_path=db_path,
            embeddings_path=emb_path,
        )

    assert call_order == ["init_db", "ingest", "embed", "cluster", "sentiment", "label", "summarize", "report"]
```

**Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_pipeline.py -v
```

Expected: FAIL — `ImportError`

**Step 3: Implement pipeline.py**

Create `narratio/pipeline.py`:

```python
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
    console = Console()

    console.print("[bold cyan]Narratio Pipeline[/bold cyan]")
    console.print("=" * 40)

    # 1. Init DB
    console.print("\n[bold]1/7 Initializing database...[/bold]")
    init_db(db_path)
    console.print("  ✓ Database ready")

    # 2. Ingest
    console.print("\n[bold]2/7 Ingesting articles from Finnhub...[/bold]")
    client = finnhub.Client(api_key=finnhub_key)
    count = ingest_articles(client, db_path, max_pages=max_pages)
    console.print(f"  ✓ Ingested {count} new articles")

    # 3. Embed
    console.print("\n[bold]3/7 Generating embeddings...[/bold]")
    # First, ensure article_analysis rows exist for new articles
    _ensure_analysis_rows(db_path)
    count = embed_articles(db_path, embeddings_path, openrouter_key)
    console.print(f"  ✓ Embedded {count} articles")

    # 4. Cluster
    console.print("\n[bold]4/7 Clustering articles...[/bold]")
    n_clusters = cluster_articles(db_path, embeddings_path)
    console.print(f"  ✓ Found {n_clusters} clusters")

    # 5. Sentiment
    console.print("\n[bold]5/7 Analyzing sentiment...[/bold]")
    count = analyze_sentiment(db_path, openrouter_key)
    console.print(f"  ✓ Scored {count} articles")

    # 6. Label
    console.print("\n[bold]6/7 Labeling narratives...[/bold]")
    n_narratives = label_clusters(db_path, embeddings_path, openrouter_key)
    console.print(f"  ✓ Labeled {n_narratives} narratives")

    # 7. Summarize
    console.print("\n[bold]7/7 Generating summaries...[/bold]")
    n_weeks = summarize_narratives(db_path, openrouter_key)
    console.print(f"  ✓ Generated {n_weeks} weekly summaries")

    # Report
    console.print("\n" + "=" * 40)
    report = generate_report(db_path)
    console.print(report)


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
```

**Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_pipeline.py -v
```

Expected: 1 passed.

**Step 5: Run full test suite**

```bash
uv run pytest tests/ -v
```

Expected: All tests pass.

**Step 6: Commit**

```bash
git add narratio/pipeline.py tests/test_pipeline.py
git commit -m "feat: pipeline orchestrator with CLI entry point"
```

---

### Task 11: End-to-End Verification

**No new files.** This task runs the pipeline against real APIs.

**Step 1: Set up .env**

```bash
cp .env.example .env
# Edit .env with real FINNHUB_API_KEY and OPENROUTER_API_KEY
```

**Step 2: Run the pipeline with limited pages (smoke test)**

```bash
uv run narratio --help  # Verify CLI works (will fail since no --help yet, but should show import errors if any)
uv run python -m narratio.pipeline  # Run the full pipeline
```

Alternatively, for a smaller test:

```python
# Quick test: run with max_pages=2 to ingest just ~200 articles
from narratio.config import get_config
from narratio.pipeline import run_pipeline

cfg = get_config()
run_pipeline(cfg.finnhub_api_key, cfg.openrouter_api_key, max_pages=2)
```

**Step 3: Review the report output**

Verify:
- At least 5+ narratives discovered
- Labels are coherent (e.g., "Fed Rate Expectations", not "Random Word Salad")
- Share of attention percentages sum to ~100% per week
- Z-scores are non-trivial (some > 1.0)
- Summaries read like sensible financial commentary

**Step 4: Final commit**

```bash
git add -A
git commit -m "feat: Phase 0 pipeline proof complete"
```
