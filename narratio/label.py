"""Narrative labeling via OpenRouter (Gemini Flash).

Uses centroid-based matching to preserve existing narratives across re-runs.
Supports many-to-one matching (multiple clusters can map to one narrative),
dormancy/re-emergence, and max narrative cap enforcement.
"""

import logging
import numpy as np
import httpx
from datetime import datetime
from narratio.db import get_connection

logger = logging.getLogger(__name__)

OPENROUTER_CHAT_URL = "https://openrouter.ai/api/v1/chat/completions"


def _call_openrouter_chat(messages: list[dict], api_key: str, model: str) -> dict:
    """Send a chat completion request to OpenRouter."""
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
    """Build a prompt asking the LLM to generate a short narrative label."""
    headlines_text = "\n".join(f"- {h}" for h in headlines[:10])
    return f"""These headlines belong to the same financial news cluster. Generate a short, descriptive label (3-6 words) that captures the common theme.

Headlines:
{headlines_text}

Return ONLY the label, nothing else. Example: "Fed Rate Cut Expectations" or "China Property Crisis"."""


def _get_cluster_dates(conn, cluster_id: int, cluster_col: str = "merged_cluster_id") -> tuple[str, str]:
    """Get first_seen and last_seen dates for a cluster."""
    dates = conn.execute(
        f"""SELECT MIN(a.published_at) as first, MAX(a.published_at) as last
           FROM articles a JOIN article_analysis aa ON aa.article_id = a.id
           WHERE aa.{cluster_col} = ?""",
        (cluster_id,),
    ).fetchone()
    first_seen = datetime.fromisoformat(dates["first"].replace("+0000", "+00:00")).strftime("%Y-%m-%d")
    last_seen = datetime.fromisoformat(dates["last"].replace("+0000", "+00:00")).strftime("%Y-%m-%d")
    return first_seen, last_seen


def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Compute cosine similarity between two vectors."""
    denom = np.linalg.norm(a) * np.linalg.norm(b)
    if denom < 1e-9:
        return 0.0
    return float(np.dot(a, b) / denom)


def label_clusters(
    db_path: str,
    embeddings_path: str,
    api_key: str,
    match_threshold: float = 0.80,
    max_narratives: int = 80,
    label_model: str = "google/gemini-2.0-flash-001",
) -> int:
    """Label each cluster, matching to existing narratives where possible.

    Key changes from original:
    - Many-to-one matching: multiple clusters can match the same narrative (no matched_ids exclusion)
    - Uses merged_cluster_id (from post-clustering merge step) instead of cluster_id
    - Dormant narratives can be re-emerged if a new cluster matches them
    - Enforces max_narratives cap after labeling

    Returns the number of NEW narratives that required LLM calls.
    """
    conn = get_connection(db_path)
    embeddings = np.load(embeddings_path)

    # --- Phase 1: Compute centroids for existing narratives (both active and dormant) ---
    existing_narratives = conn.execute("SELECT id, label, status FROM narratives").fetchall()
    logger.info("Found %d existing narratives", len(existing_narratives))
    old_centroids: dict[int, np.ndarray] = {}
    for n in existing_narratives:
        indices = conn.execute(
            "SELECT aa.embedding_index FROM article_analysis aa WHERE aa.narrative_id = ? AND aa.embedding_index IS NOT NULL",
            (n["id"],),
        ).fetchall()
        if indices:
            vecs = embeddings[[r["embedding_index"] for r in indices]]
            old_centroids[n["id"]] = vecs.mean(axis=0)

    # --- Phase 2: Clear narrative_id assignments (will reassign), but keep narratives + narrative_weeks ---
    conn.execute("UPDATE article_analysis SET narrative_id = NULL")
    conn.commit()

    # --- Phase 3: For each merged cluster, match to existing narrative or create new ---
    # Use merged_cluster_id if available, fall back to cluster_id
    has_merged = conn.execute(
        "SELECT COUNT(*) FROM article_analysis WHERE merged_cluster_id IS NOT NULL"
    ).fetchone()[0]
    cluster_col = "merged_cluster_id" if has_merged > 0 else "cluster_id"

    clusters = conn.execute(
        f"SELECT DISTINCT {cluster_col} as cid FROM article_analysis WHERE {cluster_col} IS NOT NULL ORDER BY cid"
    ).fetchall()
    logger.info("Processing %d clusters (using %s)", len(clusters), cluster_col)

    matched_narrative_ids: set[int] = set()  # Track which narratives got matched (for dormancy)
    n_labeled = 0
    n_matched = 0

    for row in clusters:
        cid = row["cid"]

        # Compute new cluster centroid
        c_indices = conn.execute(
            f"SELECT embedding_index FROM article_analysis WHERE {cluster_col} = ? AND embedding_index IS NOT NULL",
            (cid,),
        ).fetchall()
        if not c_indices:
            continue

        idx_list = [r["embedding_index"] for r in c_indices]
        c_vecs = embeddings[idx_list]
        new_centroid = c_vecs.mean(axis=0)

        # Find best matching existing narrative — many-to-one (no exclusion set)
        best_nid, best_sim = None, 0.0
        for nid, old_c in old_centroids.items():
            sim = _cosine_similarity(new_centroid, old_c)
            if sim > best_sim and sim >= match_threshold:
                best_sim = sim
                best_nid = nid

        if best_nid is not None:
            # Reuse existing narrative (may already be matched by another cluster — that's fine)
            matched_narrative_ids.add(best_nid)
            narrative_id = best_nid
            n_matched += 1
            dates = _get_cluster_dates(conn, cid, cluster_col)
            conn.execute(
                """UPDATE narratives
                   SET first_seen = CASE WHEN first_seen < ? THEN first_seen ELSE ? END,
                       last_seen = CASE WHEN last_seen > ? THEN last_seen ELSE ? END,
                       status = 'active',
                       centroid_embedding_index = ?
                   WHERE id = ?""",
                (dates[0], dates[0], dates[1], dates[1], idx_list[0], narrative_id),
            )
        else:
            # New cluster — needs LLM labeling
            articles = conn.execute(
                f"""SELECT a.headline FROM articles a
                   JOIN article_analysis aa ON aa.article_id = a.id
                   WHERE aa.{cluster_col} = ?
                   ORDER BY a.published_at DESC LIMIT 10""",
                (cid,),
            ).fetchall()
            headlines = [a["headline"] for a in articles]
            messages = [{"role": "user", "content": _build_label_prompt(headlines)}]
            result = _call_openrouter_chat(messages, api_key, model=label_model)
            label = result["choices"][0]["message"]["content"].strip().strip('"').strip("'")

            dates = _get_cluster_dates(conn, cid, cluster_col)
            cursor = conn.execute(
                """INSERT INTO narratives (label, first_seen, last_seen, status, centroid_embedding_index)
                   VALUES (?, ?, ?, 'active', ?)""",
                (label, dates[0], dates[1], idx_list[0]),
            )
            narrative_id = cursor.lastrowid
            matched_narrative_ids.add(narrative_id)
            # Add centroid to old_centroids so subsequent clusters can match via many-to-one
            old_centroids[narrative_id] = new_centroid
            n_labeled += 1

        # Assign articles to this narrative
        conn.execute(
            f"UPDATE article_analysis SET narrative_id=? WHERE {cluster_col}=?",
            (narrative_id, cid),
        )
        conn.commit()

    logger.info("Labeling: %d matched existing, %d new (LLM-labeled)", n_matched, n_labeled)

    # --- Phase 4: Dormancy — mark unmatched old narratives as dormant ---
    dormant_count = 0
    for n in existing_narratives:
        if n["id"] not in matched_narrative_ids:
            conn.execute("UPDATE narratives SET status='dormant' WHERE id=?", (n["id"],))
            dormant_count += 1
    conn.commit()
    if dormant_count:
        logger.info("Marked %d narratives as dormant", dormant_count)

    # --- Phase 5: Enforce max_narratives cap ---
    _enforce_narrative_cap(conn, max_narratives)
    conn.commit()

    conn.close()
    return n_labeled


def _enforce_narrative_cap(conn, max_narratives: int) -> None:
    """If active narrative count exceeds cap, mark lowest-significance ones as dormant."""
    active_count = conn.execute(
        "SELECT COUNT(*) FROM narratives WHERE status='active'"
    ).fetchone()[0]

    if active_count <= max_narratives:
        return

    excess = active_count - max_narratives

    # Find narratives with fewest articles (lowest significance)
    lowest = conn.execute(
        """SELECT n.id, COUNT(aa.article_id) as article_count
           FROM narratives n
           LEFT JOIN article_analysis aa ON aa.narrative_id = n.id
           WHERE n.status = 'active'
           GROUP BY n.id
           ORDER BY article_count ASC, n.id ASC
           LIMIT ?""",
        (excess,),
    ).fetchall()

    for row in lowest:
        conn.execute("UPDATE narratives SET status='dormant' WHERE id=?", (row["id"],))
