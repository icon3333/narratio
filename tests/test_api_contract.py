"""Compatibility contracts for the FastAPI/Starlette boundary."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from narratio import api


class _StartupConnection:
    def execute(self, _query: str) -> SimpleNamespace:
        return SimpleNamespace(rowcount=0)

    def commit(self) -> None:
        pass

    def close(self) -> None:
        pass


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch):
    init_db = Mock()
    compute_significance_scores = Mock()
    monkeypatch.setattr(api, "init_db", init_db)
    monkeypatch.setattr(api, "get_connection", lambda _path: _StartupConnection())
    monkeypatch.setattr(
        api, "compute_significance_scores", compute_significance_scores
    )
    api._pipeline_status.update(
        running=False, last_result=None, step=0, total_steps=0, step_label=""
    )
    api._covers_status["running"] = False

    with TestClient(api.app, raise_server_exceptions=False) as test_client:
        yield test_client, init_db, compute_significance_scores


def test_lifespan_initializes_database_and_scores(client):
    _, init_db, compute_significance_scores = client

    init_db.assert_called_once_with(api.DB_PATH)
    compute_significance_scores.assert_called_once_with(api.DB_PATH)


def test_json_route_preserves_success_and_error_contracts(client, monkeypatch):
    test_client, _, _ = client
    monkeypatch.setattr(api, "get_stats", lambda _path: {"articles": 42})

    response = test_client.get("/api/stats")

    assert response.status_code == 200
    assert response.json() == {"articles": 42}
    assert response.headers["content-type"].startswith("application/json")

    def fail(_path: str):
        raise RuntimeError("database unavailable")

    monkeypatch.setattr(api, "get_stats", fail)
    response = test_client.get("/api/stats")

    assert response.status_code == 500
    assert response.json() == {"detail": "database unavailable"}


def test_path_parameter_validation_remains_structured(client):
    test_client, _, _ = client

    response = test_client.get("/api/narratives/not-an-integer")

    assert response.status_code == 422
    assert response.headers["content-type"].startswith("application/json")
    assert response.json()["detail"][0]["loc"] == ["path", "narrative_id"]


def test_cors_preflight_allows_dashboard_origin(client):
    test_client, _, _ = client

    response = test_client.options(
        "/api/stats",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"
    assert "GET" in response.headers["access-control-allow-methods"]


def test_pipeline_trigger_runs_background_task(client, monkeypatch):
    test_client, _, _ = client
    calls = []

    def run_pipeline() -> None:
        calls.append("run")
        api._pipeline_status["running"] = False

    monkeypatch.setattr(api, "_run_pipeline_task", run_pipeline)

    response = test_client.post("/api/pipeline/run")

    assert response.status_code == 200
    assert response.json() == {"status": "started"}
    assert calls == ["run"]


def test_image_proxy_preserves_binary_response_contract(client, monkeypatch):
    test_client, _, _ = client
    requested = {}

    class FakeResponse:
        content = b"image-bytes"
        headers = {"content-type": "image/png"}

        def raise_for_status(self) -> None:
            pass

    class FakeAsyncClient:
        def __init__(self, *, timeout: int):
            requested["timeout"] = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_exc_info):
            return None

        async def get(self, url: str, **kwargs):
            requested.update(url=url, **kwargs)
            return FakeResponse()

    monkeypatch.setattr(api.httpx, "AsyncClient", FakeAsyncClient)

    response = test_client.get(
        "/api/covers/image-proxy",
        params={"url": "https://www.economist.com/example.png"},
    )

    assert response.status_code == 200
    assert response.content == b"image-bytes"
    assert response.headers["content-type"] == "image/png"
    assert response.headers["cache-control"] == "public, max-age=604800"
    assert requested["url"] == "https://www.economist.com/example.png"
    assert requested["follow_redirects"] is True
    assert requested["timeout"] == 15
