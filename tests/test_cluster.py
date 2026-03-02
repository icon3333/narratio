import numpy as np
from narratio.db import init_db, get_connection
from narratio.cluster import cluster_articles, merge_clusters, filter_relevance


def _seed_db_with_embeddings(db_path, embeddings_path, n=120):
    """Create n articles with embeddings forming 2 clusters + noise."""
    init_db(db_path)
    conn = get_connection(db_path)

    rng = np.random.default_rng(42)
    embeddings = []

    for i in range(n):
        conn.execute(
            """INSERT INTO articles (source_id, headline, summary, source, url, published_at, category)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (f"nyt-{i}", f"Headline {i}", f"Summary {i}", "test", "http://test.com", "2025-12-01T00:00:00+0000", "general"),
        )
        conn.execute(
            "INSERT INTO article_analysis (article_id, embedding_index) VALUES (?, ?)",
            (i + 1, i),
        )

        if i < n * 2 // 5:
            emb = np.zeros(1536, dtype=np.float32)
            emb[0] = 1.0
            emb += rng.normal(0, 0.05, 1536).astype(np.float32)
        elif i < n * 4 // 5:
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
    _seed_db_with_embeddings(db_path, emb_path, n=120)

    # Use smaller min_cluster_size for test data (only 120 articles)
    n_clusters = cluster_articles(db_path, emb_path, min_cluster_size=8, min_samples=5)

    assert n_clusters >= 2

    conn = get_connection(db_path)
    rows = conn.execute(
        "SELECT cluster_id FROM article_analysis WHERE cluster_id IS NOT NULL"
    ).fetchall()
    conn.close()

    assert len(rows) >= 40  # At least the 2 tight clusters


def test_cluster_only_relevant_articles(tmp_path):
    """cluster_articles should skip articles with is_relevant=0."""
    db_path = str(tmp_path / "test.db")
    emb_path = str(tmp_path / "embeddings.npy")
    _seed_db_with_embeddings(db_path, emb_path, n=120)

    # Mark first 20 articles as irrelevant
    conn = get_connection(db_path)
    for i in range(1, 21):
        conn.execute("UPDATE article_analysis SET is_relevant = 0 WHERE article_id = ?", (i,))
    conn.commit()
    conn.close()

    n_clusters = cluster_articles(db_path, emb_path, min_cluster_size=8, min_samples=5)
    assert n_clusters >= 1

    conn = get_connection(db_path)
    # Irrelevant articles should not be clustered
    irrelevant_clustered = conn.execute(
        "SELECT COUNT(*) FROM article_analysis WHERE is_relevant = 0 AND cluster_id IS NOT NULL"
    ).fetchone()[0]
    conn.close()
    assert irrelevant_clustered == 0


def test_merge_clusters(tmp_path):
    """merge_clusters should merge clusters with similar centroids."""
    db_path = str(tmp_path / "test.db")
    emb_path = str(tmp_path / "embeddings.npy")

    init_db(db_path)
    conn = get_connection(db_path)

    rng = np.random.default_rng(42)
    embeddings = []

    # Create 3 clusters: 2 very similar (should merge), 1 different
    for i in range(60):
        conn.execute(
            """INSERT INTO articles (source_id, headline, summary, source, url, published_at, category)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (f"nyt-{i}", f"Headline {i}", f"Summary {i}", "test", "http://test.com", "2025-12-01T00:00:00+0000", "general"),
        )

        if i < 20:
            # Cluster 0: centered at [1, 0, 0, ...]
            emb = np.zeros(1536, dtype=np.float32)
            emb[0] = 1.0
            emb += rng.normal(0, 0.01, 1536).astype(np.float32)
            cluster_id = 0
        elif i < 40:
            # Cluster 1: very similar to cluster 0 (should merge)
            emb = np.zeros(1536, dtype=np.float32)
            emb[0] = 0.98
            emb[2] = 0.02
            emb += rng.normal(0, 0.01, 1536).astype(np.float32)
            cluster_id = 1
        else:
            # Cluster 2: different direction (should NOT merge)
            emb = np.zeros(1536, dtype=np.float32)
            emb[1] = 1.0
            emb += rng.normal(0, 0.01, 1536).astype(np.float32)
            cluster_id = 2

        conn.execute(
            "INSERT INTO article_analysis (article_id, embedding_index, cluster_id) VALUES (?, ?, ?)",
            (i + 1, i, cluster_id),
        )
        embeddings.append(emb)

    conn.commit()
    conn.close()

    np.save(emb_path, np.array(embeddings, dtype=np.float32))

    n_merged = merge_clusters(db_path, emb_path, merge_threshold=0.80)
    # Clusters 0 and 1 should merge, cluster 2 stays separate → 2 merged clusters
    assert n_merged == 2

    conn = get_connection(db_path)
    # Check that articles from clusters 0 and 1 share the same merged_cluster_id
    merged_0 = conn.execute(
        "SELECT DISTINCT merged_cluster_id FROM article_analysis WHERE cluster_id = 0"
    ).fetchall()
    merged_1 = conn.execute(
        "SELECT DISTINCT merged_cluster_id FROM article_analysis WHERE cluster_id = 1"
    ).fetchall()
    merged_2 = conn.execute(
        "SELECT DISTINCT merged_cluster_id FROM article_analysis WHERE cluster_id = 2"
    ).fetchall()
    conn.close()

    assert len(merged_0) == 1
    assert len(merged_1) == 1
    assert len(merged_2) == 1
    assert merged_0[0]["merged_cluster_id"] == merged_1[0]["merged_cluster_id"]
    assert merged_0[0]["merged_cluster_id"] != merged_2[0]["merged_cluster_id"]


def test_preloaded_embeddings_accepted(tmp_path):
    """All three clustering functions accept a pre-loaded embeddings kwarg."""
    db_path = str(tmp_path / "test.db")
    emb_path = str(tmp_path / "embeddings.npy")
    _seed_db_with_embeddings(db_path, emb_path, n=120)

    preloaded = np.load(emb_path)

    # filter_relevance with preloaded embeddings
    n_marked = filter_relevance(db_path, emb_path, embeddings=preloaded)
    assert n_marked >= 0

    # cluster_articles with preloaded embeddings
    n_clusters = cluster_articles(
        db_path, emb_path, min_cluster_size=8, min_samples=5, embeddings=preloaded
    )
    assert n_clusters >= 1

    # merge_clusters with preloaded embeddings
    n_merged = merge_clusters(db_path, emb_path, embeddings=preloaded)
    assert n_merged >= 1


def test_filter_relevance_marks_non_financial(tmp_path):
    """filter_relevance should mark articles from non-financial sections as irrelevant."""
    db_path = str(tmp_path / "test.db")
    emb_path = str(tmp_path / "embeddings.npy")

    init_db(db_path)
    conn = get_connection(db_path)

    rng = np.random.default_rng(42)
    embeddings = []

    # Financial article
    conn.execute(
        """INSERT INTO articles (source_id, headline, summary, source, url, published_at, category)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        ("g-1", "Fed raises rates", "summary", "test", "http://test.com", "2025-12-01T00:00:00+0000", "Business"),
    )
    conn.execute("INSERT INTO article_analysis (article_id, embedding_index) VALUES (1, 0)")
    embeddings.append(rng.normal(0, 1, 1536).astype(np.float32))

    # Non-financial article (Science section)
    conn.execute(
        """INSERT INTO articles (source_id, headline, summary, source, url, published_at, category)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        ("g-2", "New species found", "summary", "test", "http://test.com", "2025-12-01T00:00:00+0000", "Science"),
    )
    conn.execute("INSERT INTO article_analysis (article_id, embedding_index) VALUES (2, 1)")
    embeddings.append(rng.normal(0, 1, 1536).astype(np.float32))

    # Non-financial article (Environment)
    conn.execute(
        """INSERT INTO articles (source_id, headline, summary, source, url, published_at, category)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        ("g-3", "Forest conservation efforts", "summary", "test", "http://test.com", "2025-12-01T00:00:00+0000", "Environment"),
    )
    conn.execute("INSERT INTO article_analysis (article_id, embedding_index) VALUES (3, 2)")
    embeddings.append(rng.normal(0, 1, 1536).astype(np.float32))

    conn.commit()
    conn.close()

    np.save(emb_path, np.array(embeddings, dtype=np.float32))

    n_marked = filter_relevance(db_path, emb_path)
    assert n_marked >= 2  # Science and Environment articles

    conn = get_connection(db_path)
    relevant = conn.execute(
        "SELECT article_id FROM article_analysis WHERE is_relevant = 1"
    ).fetchall()
    irrelevant = conn.execute(
        "SELECT article_id FROM article_analysis WHERE is_relevant = 0"
    ).fetchall()
    conn.close()

    assert len(relevant) >= 1  # Business article stays relevant
    assert len(irrelevant) >= 2  # Science + Environment marked irrelevant
