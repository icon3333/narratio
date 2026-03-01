import numpy as np
from narratio.db import init_db, get_connection
from narratio.cluster import cluster_articles


def _seed_db_with_embeddings(db_path, embeddings_path, n=60):
    """Create n articles with embeddings forming 2 clusters + noise."""
    init_db(db_path)
    conn = get_connection(db_path)

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

        if i < 25:
            emb = np.zeros(1536, dtype=np.float32)
            emb[0] = 1.0
            emb += rng.normal(0, 0.05, 1536).astype(np.float32)
        elif i < 50:
            emb = np.zeros(1536, dtype=np.float32)
            emb[1] = 1.0
            emb += rng.normal(0, 0.05, 1536).astype(np.float32)
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
