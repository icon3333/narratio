import numpy as np
from unittest.mock import patch
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

    conn = get_connection(db_path)
    for i in range(3):
        conn.execute(
            """INSERT INTO articles (nyt_id, headline, summary, source, url, published_at, category)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (f"nyt-{i}", f"Headline {i}", f"Summary {i}", "test", "http://test.com", "2025-12-01T00:00:00+0000", "general"),
        )
        conn.execute(
            "INSERT INTO article_analysis (article_id) VALUES (?)",
            (i + 1,),
        )
    conn.commit()
    conn.close()

    fake_embeddings = np.random.rand(3, 1536).tolist()
    mock_response = {
        "data": [{"embedding": fake_embeddings[i], "index": i} for i in range(3)]
    }

    with patch("narratio.embed._call_openrouter_embed") as mock_call:
        mock_call.return_value = mock_response
        count = embed_articles(db_path, embeddings_path, "fake-key", batch_size=10)

    assert count == 3

    emb = np.load(embeddings_path)
    assert emb.shape == (3, 1536)

    conn = get_connection(db_path)
    rows = conn.execute("SELECT embedding_index FROM article_analysis ORDER BY article_id").fetchall()
    conn.close()
    indices = [r[0] for r in rows]
    assert indices == [0, 1, 2]
