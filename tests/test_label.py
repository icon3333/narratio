import numpy as np
from unittest.mock import patch
from narratio.db import init_db, get_connection
from narratio.label import label_clusters, _build_label_prompt, _cosine_similarity


def test_build_label_prompt():
    headlines = ["Fed cuts rates", "Rate cut expectations rise", "Markets rally on rate hopes"]
    prompt = _build_label_prompt(headlines)
    assert "Fed cuts rates" in prompt
    assert "3-6 word" in prompt.lower() or "short" in prompt.lower()


def test_cosine_similarity():
    a = np.array([1.0, 0.0, 0.0])
    b = np.array([1.0, 0.0, 0.0])
    assert abs(_cosine_similarity(a, b) - 1.0) < 1e-6

    c = np.array([0.0, 1.0, 0.0])
    assert abs(_cosine_similarity(a, c)) < 1e-6


def _setup_db_with_cluster(tmp_path, n_articles=20, use_merged=False):
    """Helper: create DB with articles in cluster 0, return (db_path, emb_path)."""
    db_path = str(tmp_path / "test.db")
    emb_path = str(tmp_path / "embeddings.npy")
    init_db(db_path)
    conn = get_connection(db_path)

    embeddings = []
    for i in range(n_articles):
        conn.execute(
            """INSERT INTO articles (source_id, headline, summary, source, url, published_at, category)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (f"nyt-{i}", f"Fed rate cut headline {i}", "summary", "test", "http://test.com", "2025-12-01T00:00:00+0000", "general"),
        )
        merged_cid = 0 if use_merged else None
        conn.execute(
            "INSERT INTO article_analysis (article_id, embedding_index, cluster_id, merged_cluster_id) VALUES (?, ?, ?, ?)",
            (i + 1, i, 0, merged_cid),
        )
        # Use a consistent base vector + small noise so centroids are stable
        emb = np.array([1.0, 0.0, 0.0] + [0.0] * 1533, dtype=np.float32)
        emb += np.random.rand(1536).astype(np.float32) * 0.01
        embeddings.append(emb)

    conn.commit()
    conn.close()
    np.save(emb_path, np.array(embeddings))
    return db_path, emb_path


def test_label_clusters_creates_narratives(tmp_path):
    db_path, emb_path = _setup_db_with_cluster(tmp_path)

    fake_response = {
        "choices": [{"message": {"content": "Fed Rate Cut Expectations"}}]
    }

    with patch("narratio.label._call_openrouter_chat") as mock_call:
        mock_call.return_value = fake_response
        n = label_clusters(db_path, emb_path, "fake-key")

    assert n == 1  # one new cluster → one LLM call

    conn = get_connection(db_path)
    narrative = conn.execute("SELECT label FROM narratives").fetchone()
    conn.close()
    assert narrative is not None
    assert "Fed" in narrative["label"] or "Rate" in narrative["label"]


def test_label_clusters_idempotent_rerun(tmp_path):
    """Re-running label_clusters with same data should match existing narrative (0 LLM calls)."""
    db_path, emb_path = _setup_db_with_cluster(tmp_path)

    fake_response = {
        "choices": [{"message": {"content": "Fed Rate Cut Expectations"}}]
    }

    # First run: creates 1 narrative, 1 LLM call
    with patch("narratio.label._call_openrouter_chat") as mock_call:
        mock_call.return_value = fake_response
        n1 = label_clusters(db_path, emb_path, "fake-key")
        assert n1 == 1
        assert mock_call.call_count == 1

    conn = get_connection(db_path)
    narrative_after_first = conn.execute("SELECT id, label FROM narratives WHERE status='active'").fetchall()
    conn.close()
    assert len(narrative_after_first) == 1
    original_id = narrative_after_first[0]["id"]

    # Second run (same data, same cluster): should match existing narrative, 0 LLM calls
    with patch("narratio.label._call_openrouter_chat") as mock_call:
        mock_call.return_value = fake_response
        n2 = label_clusters(db_path, emb_path, "fake-key")
        assert n2 == 0  # no new narratives
        assert mock_call.call_count == 0  # no LLM calls

    conn = get_connection(db_path)
    narrative_after_second = conn.execute("SELECT id, label FROM narratives WHERE status='active'").fetchall()
    assigned = conn.execute("SELECT narrative_id FROM article_analysis WHERE narrative_id IS NOT NULL").fetchall()
    conn.close()

    assert len(narrative_after_second) == 1
    assert narrative_after_second[0]["id"] == original_id  # same ID preserved
    assert len(assigned) == 20  # all articles still assigned


def test_label_clusters_many_to_one(tmp_path):
    """Multiple clusters can match the same existing narrative."""
    db_path = str(tmp_path / "test.db")
    emb_path = str(tmp_path / "embeddings.npy")
    init_db(db_path)
    conn = get_connection(db_path)

    embeddings = []
    # Create 2 clusters with very similar embeddings
    for i in range(40):
        cluster_id = 0 if i < 20 else 1
        conn.execute(
            """INSERT INTO articles (source_id, headline, summary, source, url, published_at, category)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (f"nyt-{i}", f"Fed rate headline {i}", "summary", "test", "http://test.com", "2025-12-01T00:00:00+0000", "general"),
        )
        conn.execute(
            "INSERT INTO article_analysis (article_id, embedding_index, cluster_id) VALUES (?, ?, ?)",
            (i + 1, i, cluster_id),
        )
        # Very similar embeddings for both clusters
        emb = np.array([1.0, 0.0, 0.0] + [0.0] * 1533, dtype=np.float32)
        emb += np.random.rand(1536).astype(np.float32) * 0.01
        embeddings.append(emb)

    conn.commit()
    conn.close()
    np.save(emb_path, np.array(embeddings))

    fake_response = {
        "choices": [{"message": {"content": "Fed Rate Cut Expectations"}}]
    }

    # First run: creates 1 narrative from first cluster, second cluster matches it
    with patch("narratio.label._call_openrouter_chat") as mock_call:
        mock_call.return_value = fake_response
        n = label_clusters(db_path, emb_path, "fake-key", match_threshold=0.80)

    # Should create 1 new narrative (cluster 0), cluster 1 matches it via many-to-one
    assert n == 1

    conn = get_connection(db_path)
    active = conn.execute("SELECT COUNT(*) FROM narratives WHERE status='active'").fetchone()[0]
    assigned = conn.execute("SELECT COUNT(*) FROM article_analysis WHERE narrative_id IS NOT NULL").fetchone()[0]
    conn.close()

    assert active == 1  # both clusters → same narrative
    assert assigned == 40  # all articles assigned


def test_label_clusters_dormancy(tmp_path):
    """Narratives with no matching clusters become dormant."""
    db_path, emb_path = _setup_db_with_cluster(tmp_path)

    fake_response = {
        "choices": [{"message": {"content": "Fed Rate Cut Expectations"}}]
    }

    # First run
    with patch("narratio.label._call_openrouter_chat") as mock_call:
        mock_call.return_value = fake_response
        label_clusters(db_path, emb_path, "fake-key")

    # Add NEW articles with different embeddings in a new cluster,
    # and remove old articles from clustering (set cluster_id=NULL)
    conn = get_connection(db_path)
    # Detach old articles from any cluster
    conn.execute("UPDATE article_analysis SET cluster_id = NULL, merged_cluster_id = NULL")

    embeddings = list(np.load(emb_path))

    # Add 20 new articles in a completely different direction
    for i in range(20, 40):
        conn.execute(
            """INSERT INTO articles (source_id, headline, summary, source, url, published_at, category)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (f"nyt-{i}", f"New topic headline {i}", "summary", "test", "http://test.com", "2025-12-01T00:00:00+0000", "general"),
        )
        conn.execute(
            "INSERT INTO article_analysis (article_id, embedding_index, cluster_id) VALUES (?, ?, ?)",
            (i + 1, i, 99),
        )
        emb = np.zeros(1536, dtype=np.float32)
        emb[500] = 1.0  # completely different direction from original
        emb += np.random.rand(1536).astype(np.float32) * 0.01
        embeddings.append(emb)

    conn.commit()
    conn.close()
    np.save(emb_path, np.array(embeddings, dtype=np.float32))

    # Second run: old narrative won't match new cluster → dormant
    with patch("narratio.label._call_openrouter_chat") as mock_call:
        mock_call.return_value = {"choices": [{"message": {"content": "New Topic"}}]}
        label_clusters(db_path, emb_path, "fake-key")

    conn = get_connection(db_path)
    dormant = conn.execute("SELECT COUNT(*) FROM narratives WHERE status='dormant'").fetchone()[0]
    conn.close()
    assert dormant >= 1


def test_label_clusters_uses_merged_cluster_id(tmp_path):
    """label_clusters should use merged_cluster_id when available."""
    db_path, emb_path = _setup_db_with_cluster(tmp_path, use_merged=True)

    fake_response = {
        "choices": [{"message": {"content": "Fed Rate Cut Expectations"}}]
    }

    with patch("narratio.label._call_openrouter_chat") as mock_call:
        mock_call.return_value = fake_response
        n = label_clusters(db_path, emb_path, "fake-key")

    assert n == 1

    conn = get_connection(db_path)
    assigned = conn.execute("SELECT COUNT(*) FROM article_analysis WHERE narrative_id IS NOT NULL").fetchall()
    conn.close()
    assert assigned[0][0] == 20
