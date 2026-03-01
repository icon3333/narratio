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
        metric="euclidean",
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
