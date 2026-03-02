"""Configuration from environment variables."""

import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass(frozen=True)
class Config:
    # API keys
    openrouter_api_key: str
    nyt_api_key: str | None = None
    guardian_api_key: str | None = None

    # Paths
    db_path: str = "data/narratio.db"
    embeddings_path: str = "data/embeddings.npy"

    # Clustering
    min_cluster_size: int = 150
    min_samples: int = 25
    umap_n_components: int = 50
    umap_n_neighbors: int = 30
    umap_min_dist: float = 0.0
    merge_threshold: float = 0.80
    match_threshold: float = 0.80
    max_narratives: int = 80
    relevance_threshold: float = 0.30

    # Models
    embed_model: str = "openai/text-embedding-3-small"
    label_model: str = "google/gemini-2.0-flash-001"
    summary_model: str = "google/gemini-2.0-flash-001"
    sentiment_model: str = "google/gemini-2.0-flash-001"

    # Pipeline
    summary_top_n: int = 20
    z_score_window: int = 8


def get_config() -> Config:
    load_dotenv()
    openrouter_key = os.environ.get("OPENROUTER_API_KEY")

    if not openrouter_key:
        raise ValueError("OPENROUTER_API_KEY environment variable is required")

    nyt_key = os.environ.get("NYT_API_KEY") or None
    guardian_key = os.environ.get("GUARDIAN_API_KEY") or None

    if not nyt_key and not guardian_key:
        raise ValueError("At least one of NYT_API_KEY or GUARDIAN_API_KEY is required")

    return Config(
        openrouter_api_key=openrouter_key,
        nyt_api_key=nyt_key,
        guardian_api_key=guardian_key,
        db_path=os.environ.get("NARRATIO_DB_PATH", "data/narratio.db"),
        embeddings_path=os.environ.get("NARRATIO_EMBEDDINGS_PATH", "data/embeddings.npy"),
        min_cluster_size=int(os.environ.get("NARRATIO_MIN_CLUSTER_SIZE", 150)),
        min_samples=int(os.environ.get("NARRATIO_MIN_SAMPLES", 25)),
        umap_n_components=int(os.environ.get("NARRATIO_UMAP_N_COMPONENTS", 50)),
        umap_n_neighbors=int(os.environ.get("NARRATIO_UMAP_N_NEIGHBORS", 30)),
        umap_min_dist=float(os.environ.get("NARRATIO_UMAP_MIN_DIST", 0.0)),
        merge_threshold=float(os.environ.get("NARRATIO_MERGE_THRESHOLD", 0.80)),
        match_threshold=float(os.environ.get("NARRATIO_MATCH_THRESHOLD", 0.80)),
        max_narratives=int(os.environ.get("NARRATIO_MAX_NARRATIVES", 80)),
        relevance_threshold=float(os.environ.get("NARRATIO_RELEVANCE_THRESHOLD", 0.30)),
        embed_model=os.environ.get("NARRATIO_EMBED_MODEL", "openai/text-embedding-3-small"),
        label_model=os.environ.get("NARRATIO_LABEL_MODEL", "google/gemini-2.0-flash-001"),
        summary_model=os.environ.get("NARRATIO_SUMMARY_MODEL", "google/gemini-2.0-flash-001"),
        sentiment_model=os.environ.get("NARRATIO_SENTIMENT_MODEL", "google/gemini-2.0-flash-001"),
        summary_top_n=int(os.environ.get("NARRATIO_SUMMARY_TOP_N", 20)),
        z_score_window=int(os.environ.get("NARRATIO_Z_SCORE_WINDOW", 8)),
    )
