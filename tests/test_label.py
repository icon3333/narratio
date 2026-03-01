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
