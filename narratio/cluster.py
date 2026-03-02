"""HDBSCAN clustering of article embeddings with UMAP dimensionality reduction.

Includes post-clustering centroid merge and embedding-space relevance filtering.
"""

import logging
from collections import defaultdict
import numpy as np
import hdbscan
import umap
from sklearn.cluster import AgglomerativeClustering
from sklearn.preprocessing import normalize
from narratio.db import get_connection

logger = logging.getLogger(__name__)


def filter_relevance(
    db_path: str,
    embeddings_path: str,
    relevance_threshold: float = 0.30,
    *,
    embeddings: np.ndarray | None = None,
) -> int:
    """Mark articles as irrelevant if their embedding is too far from the financial reference vector.

    Uses cosine similarity between each article's embedding and the mean embedding
    of curated financial reference headlines. Articles below the threshold get
    is_relevant=0 and are excluded from clustering.

    Returns the number of articles marked irrelevant.
    """
    conn = get_connection(db_path)

    count = conn.execute(
        """SELECT COUNT(*) FROM article_analysis
           WHERE embedding_index IS NOT NULL AND is_relevant = 1"""
    ).fetchone()[0]

    if count == 0:
        conn.close()
        return 0

    if embeddings is None:
        embeddings = np.load(embeddings_path)

    # Section-based filter: bulk UPDATE for non-financial Guardian sections
    non_financial_sections = ("Science", "Environment", "Global development")
    cursor = conn.execute(
        """UPDATE article_analysis SET is_relevant = 0
           WHERE article_id IN (
               SELECT aa.article_id FROM article_analysis aa
               JOIN articles a ON a.id = aa.article_id
               WHERE a.category IN (?, ?, ?) AND aa.is_relevant = 1
           )""",
        non_financial_sections,
    )
    n_marked = cursor.rowcount

    # Embedding-space filter: compute mean of all remaining relevant article embeddings
    relevant_rows = conn.execute(
        """SELECT article_id, embedding_index FROM article_analysis
           WHERE embedding_index IS NOT NULL AND is_relevant = 1"""
    ).fetchall()

    if len(relevant_rows) > 100:
        article_ids = [r["article_id"] for r in relevant_rows]
        indices = [r["embedding_index"] for r in relevant_rows]
        all_vecs = normalize(embeddings[indices])

        reference_vector = all_vecs.mean(axis=0)
        reference_vector = reference_vector / (np.linalg.norm(reference_vector) + 1e-9)

        # Vectorized similarity: matrix-vector dot product
        similarities = all_vecs @ reference_vector
        irrelevant_ids = [
            aid for aid, sim in zip(article_ids, similarities)
            if sim < relevance_threshold
        ]

        if irrelevant_ids:
            placeholders = ",".join("?" * len(irrelevant_ids))
            conn.execute(
                f"UPDATE article_analysis SET is_relevant = 0 WHERE article_id IN ({placeholders})",
                irrelevant_ids,
            )
            n_marked += len(irrelevant_ids)

    conn.commit()
    conn.close()
    logger.info("Relevance filter: marked %d articles as irrelevant", n_marked)
    return n_marked


def cluster_articles(
    db_path: str,
    embeddings_path: str,
    min_cluster_size: int = 150,
    min_samples: int = 25,
    umap_n_components: int = 50,
    umap_n_neighbors: int = 30,
    umap_min_dist: float = 0.0,
    umap_metric: str = "cosine",
    *,
    embeddings: np.ndarray | None = None,
) -> int:
    """Cluster articles using UMAP + HDBSCAN. Only clusters relevant articles."""
    conn = get_connection(db_path)

    rows = conn.execute(
        """SELECT article_id, embedding_index FROM article_analysis
           WHERE embedding_index IS NOT NULL AND is_relevant = 1
           ORDER BY article_id"""
    ).fetchall()

    if not rows:
        logger.info("No relevant articles to cluster")
        conn.close()
        return 0

    logger.info("Clustering %d relevant articles", len(rows))
    if embeddings is None:
        embeddings = np.load(embeddings_path)
    indices = [r["embedding_index"] for r in rows]
    article_ids = [r["article_id"] for r in rows]
    vectors = normalize(embeddings[indices])

    # Clamp UMAP params to valid ranges for small datasets
    n_samples = len(vectors)
    effective_n_neighbors = min(umap_n_neighbors, max(2, n_samples - 1))
    effective_n_components = min(umap_n_components, max(2, n_samples - 1))

    reducer = umap.UMAP(
        n_components=effective_n_components,
        n_neighbors=effective_n_neighbors,
        min_dist=umap_min_dist,
        metric=umap_metric,
        random_state=42,
    )
    reduced = reducer.fit_transform(vectors)

    # Clamp min_cluster_size for small datasets
    effective_min_cluster_size = min(min_cluster_size, max(2, n_samples // 3))
    effective_min_samples = min(min_samples, effective_min_cluster_size)

    clusterer = hdbscan.HDBSCAN(
        min_cluster_size=effective_min_cluster_size,
        min_samples=effective_min_samples,
        metric="euclidean",
        cluster_selection_method="eom",
    )
    labels = clusterer.fit_predict(reduced)

    for article_id, label in zip(article_ids, labels):
        cluster_id = int(label) if label >= 0 else None
        conn.execute(
            "UPDATE article_analysis SET cluster_id = ? WHERE article_id = ?",
            (cluster_id, article_id),
        )

    conn.commit()
    conn.close()

    n_clusters = len(set(labels)) - (1 if -1 in labels else 0)
    n_noise = int(sum(1 for l in labels if l == -1))
    logger.info("HDBSCAN: %d clusters found, %d noise articles", n_clusters, n_noise)
    return n_clusters


def merge_clusters(
    db_path: str,
    embeddings_path: str,
    merge_threshold: float = 0.80,
    *,
    embeddings: np.ndarray | None = None,
) -> int:
    """Merge semantically similar HDBSCAN clusters via agglomerative clustering on centroids.

    Uses original high-dimensional embeddings (not UMAP-reduced) for accurate similarity.
    Returns the number of distinct merged clusters.
    """
    conn = get_connection(db_path)

    cluster_rows = conn.execute(
        "SELECT DISTINCT cluster_id FROM article_analysis WHERE cluster_id IS NOT NULL ORDER BY cluster_id"
    ).fetchall()

    cluster_ids = [r["cluster_id"] for r in cluster_rows]
    if len(cluster_ids) <= 1:
        # Nothing to merge — copy cluster_id to merged_cluster_id
        for cid in cluster_ids:
            conn.execute(
                "UPDATE article_analysis SET merged_cluster_id = cluster_id WHERE cluster_id = ?",
                (cid,),
            )
        conn.commit()
        conn.close()
        return len(cluster_ids)

    if embeddings is None:
        embeddings = np.load(embeddings_path)

    # Bulk query: fetch all embedding indices for all clusters at once
    all_cluster_rows = conn.execute(
        "SELECT cluster_id, embedding_index FROM article_analysis WHERE cluster_id IS NOT NULL AND embedding_index IS NOT NULL"
    ).fetchall()

    cluster_indices = defaultdict(list)
    for r in all_cluster_rows:
        cluster_indices[r["cluster_id"]].append(r["embedding_index"])

    # Compute centroid for each cluster in original embedding space
    centroids = []
    for cid in cluster_ids:
        indices = cluster_indices.get(cid, [])
        if indices:
            vecs = normalize(embeddings[indices])
            centroids.append(vecs.mean(axis=0))
        else:
            centroids.append(np.zeros(embeddings.shape[1]))

    centroid_matrix = normalize(np.array(centroids))

    # Cosine distance = 1 - cosine_similarity
    distance_threshold = 1.0 - merge_threshold

    agg = AgglomerativeClustering(
        n_clusters=None,
        distance_threshold=distance_threshold,
        metric="cosine",
        linkage="average",
    )
    merge_labels = agg.fit_predict(centroid_matrix)

    # Map original cluster_id → merged_cluster_id
    for cid, merged_label in zip(cluster_ids, merge_labels):
        conn.execute(
            "UPDATE article_analysis SET merged_cluster_id = ? WHERE cluster_id = ?",
            (int(merged_label), cid),
        )

    conn.commit()
    conn.close()

    n_merged = len(set(merge_labels))
    logger.info("Cluster merge: %d raw clusters merged to %d", len(cluster_ids), n_merged)
    return n_merged
