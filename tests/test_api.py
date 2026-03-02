from fastapi.testclient import TestClient
from unittest.mock import patch
import pandas as pd
from narratio.api import app


client = TestClient(app)


def _mock_narratives_df():
    return pd.DataFrame([
        {"id": 1, "label": "Fed Rate Cuts", "article_count": 25, "first_seen": "2025-12-01", "last_seen": "2025-12-15", "status": "active"},
        {"id": 2, "label": "AI Hype", "article_count": 15, "first_seen": "2025-12-01", "last_seen": "2025-12-15", "status": "active"},
    ])


def _mock_timeline_df():
    return pd.DataFrame([
        {"narrative_id": 1, "label": "Fed Rate Cuts", "week_start": pd.Timestamp("2025-12-01"), "article_count": 10, "share_of_attention": 15.0, "z_score": 0.5, "sentiment_mean": 0.3},
        {"narrative_id": 2, "label": "AI Hype", "week_start": pd.Timestamp("2025-12-01"), "article_count": 8, "share_of_attention": 12.0, "z_score": -0.2, "sentiment_mean": -0.1},
    ])


def test_list_narratives():
    with patch("narratio.api.get_narratives_df", return_value=_mock_narratives_df()):
        resp = client.get("/api/narratives")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    assert data[0]["label"] == "Fed Rate Cuts"


def test_get_narrative():
    mock_detail = {"id": 1, "label": "Fed Rate Cuts", "first_seen": "2025-12-01", "last_seen": "2025-12-15", "status": "active", "weeks": []}
    with patch("narratio.api.get_narrative_detail", return_value=mock_detail):
        resp = client.get("/api/narratives/1")
    assert resp.status_code == 200
    assert resp.json()["label"] == "Fed Rate Cuts"


def test_get_headlines():
    mock_headlines = [{"headline": "Fed cuts rates", "source": "reuters", "url": "http://test.com", "published_at": "2025-12-01T00:00:00+0000", "sentiment_score": 0.5, "sentiment_label": "bullish"}]
    with patch("narratio.api.get_narrative_headlines", return_value=mock_headlines):
        resp = client.get("/api/narratives/1/headlines")
    assert resp.status_code == 200
    assert len(resp.json()) == 1


def test_get_timeline():
    with patch("narratio.api.get_timeline_df", return_value=_mock_timeline_df()):
        resp = client.get("/api/timeline")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2


def test_pipeline_status():
    resp = client.get("/api/pipeline/status")
    assert resp.status_code == 200
    assert "running" in resp.json()
