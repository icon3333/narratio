from unittest.mock import patch


def test_config_loads_from_env(monkeypatch):
    monkeypatch.setenv("NYT_API_KEY", "test-nyt")
    monkeypatch.setenv("GUARDIAN_API_KEY", "test-guardian")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-openrouter")

    from narratio.config import get_config
    cfg = get_config()

    assert cfg.nyt_api_key == "test-nyt"
    assert cfg.guardian_api_key == "test-guardian"
    assert cfg.openrouter_api_key == "test-openrouter"


def test_config_works_with_only_nyt(monkeypatch):
    monkeypatch.setenv("NYT_API_KEY", "test-nyt")
    monkeypatch.delenv("GUARDIAN_API_KEY", raising=False)
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-openrouter")

    from narratio.config import get_config
    with patch("narratio.config.load_dotenv"):
        cfg = get_config()

    assert cfg.nyt_api_key == "test-nyt"
    assert cfg.guardian_api_key is None


def test_config_raises_on_missing_openrouter(monkeypatch):
    monkeypatch.setenv("NYT_API_KEY", "test-nyt")
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

    from narratio.config import get_config
    import pytest

    with patch("narratio.config.load_dotenv"):
        with pytest.raises(ValueError, match="OPENROUTER_API_KEY"):
            get_config()


def test_config_raises_on_no_news_source(monkeypatch):
    monkeypatch.delenv("NYT_API_KEY", raising=False)
    monkeypatch.delenv("GUARDIAN_API_KEY", raising=False)
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-openrouter")

    from narratio.config import get_config
    import pytest

    with patch("narratio.config.load_dotenv"):
        with pytest.raises(ValueError, match="NYT_API_KEY or GUARDIAN_API_KEY"):
            get_config()


def test_config_has_clustering_params(monkeypatch):
    monkeypatch.setenv("NYT_API_KEY", "test-nyt")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-openrouter")

    from narratio.config import get_config
    cfg = get_config()

    assert cfg.min_cluster_size == 150
    assert cfg.min_samples == 25
    assert cfg.umap_n_components == 50
    assert cfg.umap_n_neighbors == 30
    assert cfg.merge_threshold == 0.80
    assert cfg.match_threshold == 0.80
    assert cfg.max_narratives == 80
    assert cfg.relevance_threshold == 0.30


def test_config_env_overrides(monkeypatch):
    monkeypatch.setenv("NYT_API_KEY", "test-nyt")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-openrouter")
    monkeypatch.setenv("NARRATIO_MIN_CLUSTER_SIZE", "200")
    monkeypatch.setenv("NARRATIO_MATCH_THRESHOLD", "0.85")

    from narratio.config import get_config
    cfg = get_config()

    assert cfg.min_cluster_size == 200
    assert cfg.match_threshold == 0.85
