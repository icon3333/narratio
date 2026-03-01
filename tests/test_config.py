from unittest.mock import patch


def test_config_loads_from_env(monkeypatch):
    monkeypatch.setenv("FINNHUB_API_KEY", "test-finnhub")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-openrouter")

    from narratio.config import get_config
    cfg = get_config()

    assert cfg.finnhub_api_key == "test-finnhub"
    assert cfg.openrouter_api_key == "test-openrouter"


def test_config_raises_on_missing_keys(monkeypatch):
    monkeypatch.delenv("FINNHUB_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

    from narratio.config import get_config
    import pytest

    with patch("narratio.config.load_dotenv"):  # prevent .env from re-loading keys
        with pytest.raises(ValueError, match="FINNHUB_API_KEY"):
            get_config()
