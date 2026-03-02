import numpy as np
from unittest.mock import patch, AsyncMock
from narratio.db import init_db, get_connection
from narratio.embed import embed_articles, _build_embed_request


def test_build_embed_request():
    texts = ["headline one", "headline two"]
    req = _build_embed_request(texts)
    assert req["model"] == "openai/text-embedding-3-small"
    assert req["input"] == texts


def test_build_embed_request_custom_model():
    texts = ["headline one"]
    req = _build_embed_request(texts, model="custom/model")
    assert req["model"] == "custom/model"


def test_embed_articles_stores_embeddings(tmp_path):
    db_path = str(tmp_path / "test.db")
    embeddings_path = str(tmp_path / "embeddings.npy")
    init_db(db_path)

    conn = get_connection(db_path)
    for i in range(3):
        conn.execute(
            """INSERT INTO articles (source_id, headline, summary, source, url, published_at, category)
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

    mock_call = AsyncMock(return_value=mock_response)
    with patch("narratio.embed._call_openrouter_embed_async", mock_call):
        count = embed_articles(db_path, embeddings_path, "fake-key", batch_size=10)

    assert count == 3

    emb = np.load(embeddings_path)
    assert emb.shape == (3, 1536)

    conn = get_connection(db_path)
    rows = conn.execute("SELECT embedding_index FROM article_analysis ORDER BY article_id").fetchall()
    conn.close()
    indices = [r[0] for r in rows]
    assert indices == [0, 1, 2]


def test_embed_articles_sequential_indices_after_batch_failure(tmp_path):
    """If a batch fails, subsequent indices should still be sequential."""
    db_path = str(tmp_path / "test.db")
    embeddings_path = str(tmp_path / "embeddings.npy")
    init_db(db_path)

    conn = get_connection(db_path)
    for i in range(6):
        conn.execute(
            """INSERT INTO articles (source_id, headline, summary, source, url, published_at, category)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (f"nyt-{i}", f"Headline {i}", f"Summary {i}", "test", "http://test.com", "2025-12-01T00:00:00+0000", "general"),
        )
        conn.execute("INSERT INTO article_analysis (article_id) VALUES (?)", (i + 1,))
    conn.commit()
    conn.close()

    fake_embeddings = np.random.rand(3, 1536).tolist()
    mock_response = {
        "data": [{"embedding": fake_embeddings[i], "index": i} for i in range(3)]
    }

    call_count = 0

    async def mock_call(client, texts, api_key, model="openai/text-embedding-3-small"):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise RuntimeError("Simulated batch failure")
        return mock_response

    with patch("narratio.embed._call_openrouter_embed_async", side_effect=mock_call):
        count = embed_articles(db_path, embeddings_path, "fake-key", batch_size=3)

    # Only 3 articles from the second batch should succeed
    assert count == 3

    conn = get_connection(db_path)
    rows = conn.execute(
        "SELECT embedding_index FROM article_analysis WHERE embedding_index IS NOT NULL ORDER BY article_id"
    ).fetchall()
    conn.close()

    # Indices should be 0, 1, 2 (sequential from start)
    indices = [r[0] for r in rows]
    assert indices == [0, 1, 2]
