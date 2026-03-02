"""Configuration from environment variables."""

import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass(frozen=True)
class Config:
    nyt_api_key: str
    openrouter_api_key: str
    db_path: str = "data/narratio.db"
    embeddings_path: str = "data/embeddings.npy"


def get_config() -> Config:
    load_dotenv()
    nyt_key = os.environ.get("NYT_API_KEY")
    openrouter_key = os.environ.get("OPENROUTER_API_KEY")

    if not nyt_key:
        raise ValueError("NYT_API_KEY environment variable is required")
    if not openrouter_key:
        raise ValueError("OPENROUTER_API_KEY environment variable is required")

    return Config(
        nyt_api_key=nyt_key,
        openrouter_api_key=openrouter_key,
    )
