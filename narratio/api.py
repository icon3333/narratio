"""FastAPI backend for Narratio dashboard."""

from fastapi import FastAPI, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path

from narratio.data import (
    get_narratives_df,
    get_timeline_df,
    get_narrative_detail,
    get_narrative_headlines,
)

DB_PATH = str(Path(__file__).parent.parent / "data" / "narratio.db")

app = FastAPI(title="Narratio API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_pipeline_status = {"running": False, "last_result": None}


@app.get("/api/narratives")
def list_narratives():
    df = get_narratives_df(DB_PATH)
    return df.to_dict(orient="records")


@app.get("/api/narratives/{narrative_id}")
def get_narrative(narrative_id: int):
    return get_narrative_detail(DB_PATH, narrative_id)


@app.get("/api/narratives/{narrative_id}/headlines")
def get_headlines(narrative_id: int, limit: int = 10):
    return get_narrative_headlines(DB_PATH, narrative_id, limit=limit)


@app.get("/api/timeline")
def get_timeline(
    mode: str = "attention",
    start: str | None = None,
    end: str | None = None,
    narratives: str | None = None,
):
    df = get_timeline_df(DB_PATH)

    if start:
        df = df[df["week_start"] >= start]
    if end:
        df = df[df["week_start"] <= end]
    if narratives:
        ids = [int(x) for x in narratives.split(",")]
        df = df[df["narrative_id"].isin(ids)]

    # Convert timestamps to strings for JSON serialization
    df["week_start"] = df["week_start"].dt.strftime("%Y-%m-%d")

    return df.to_dict(orient="records")


@app.post("/api/pipeline/run")
def trigger_pipeline(background_tasks: BackgroundTasks):
    if _pipeline_status["running"]:
        return {"status": "already_running"}

    background_tasks.add_task(_run_pipeline_task)
    return {"status": "started"}


@app.get("/api/pipeline/status")
def pipeline_status():
    return _pipeline_status


def _run_pipeline_task():
    _pipeline_status["running"] = True
    _pipeline_status["last_result"] = None
    try:
        from narratio.config import get_config
        from narratio.pipeline import run_pipeline

        cfg = get_config()
        run_pipeline(
            nyt_key=cfg.nyt_api_key,
            openrouter_key=cfg.openrouter_api_key,
            db_path=DB_PATH,
            embeddings_path=cfg.embeddings_path,
        )
        _pipeline_status["last_result"] = "success"
    except Exception as e:
        _pipeline_status["last_result"] = f"error: {e}"
    finally:
        _pipeline_status["running"] = False
