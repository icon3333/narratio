"""FastAPI backend for Narratio dashboard."""

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path

from narratio.data import (
    get_narratives_df,
    get_timeline_df,
    get_timeline_with_other,
    get_narrative_detail,
    get_narrative_headlines,
    get_articles_paginated,
    get_stats,
    compute_significance_scores,
)
from narratio.db import init_db, get_connection

logger = logging.getLogger(__name__)

DB_PATH = str(Path(__file__).parent.parent / "data" / "narratio.db")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db(DB_PATH)
    # Auto-repair corrupt z_scores and recompute significance
    try:
        conn = get_connection(DB_PATH)
        clamped = conn.execute(
            "UPDATE narrative_weeks SET z_score = 10 WHERE z_score > 10"
        ).rowcount
        clamped += conn.execute(
            "UPDATE narrative_weeks SET z_score = -10 WHERE z_score < -10"
        ).rowcount
        conn.commit()
        conn.close()
        if clamped:
            logger.info("Clamped %d corrupt z_score values to [-10, 10]", clamped)
        compute_significance_scores(DB_PATH)
        logger.info("Recomputed significance scores on startup")
    except Exception as e:
        logger.warning("Startup z_score repair skipped: %s", e)
    yield


app = FastAPI(title="Narratio API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_pipeline_status = {"running": False, "last_result": None, "step": 0, "total_steps": 0, "step_label": ""}
_pipeline_lock = asyncio.Lock()


@app.get("/api/narratives")
def list_narratives():
    try:
        df = get_narratives_df(DB_PATH)
        return df.to_dict(orient="records")
    except Exception as e:
        logger.error("Failed to list narratives: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/narratives/{narrative_id}")
def get_narrative(narrative_id: int):
    try:
        result = get_narrative_detail(DB_PATH, narrative_id)
        if result is None:
            raise HTTPException(status_code=404, detail="Narrative not found")
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get narrative %d: %s", narrative_id, e)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/narratives/{narrative_id}/headlines")
def get_headlines(narrative_id: int, limit: int = 10):
    try:
        return get_narrative_headlines(DB_PATH, narrative_id, limit=limit)
    except Exception as e:
        logger.error("Failed to get headlines for narrative %d: %s", narrative_id, e)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/articles")
def list_articles(
    page: int = 1,
    per_page: int = 50,
    source: str | None = None,
    search: str | None = None,
):
    try:
        return get_articles_paginated(DB_PATH, page=page, per_page=per_page, source=source, search=search)
    except Exception as e:
        logger.error("Failed to list articles: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/stats")
def stats():
    try:
        return get_stats(DB_PATH)
    except Exception as e:
        logger.error("Failed to get stats: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/timeline")
def get_timeline(
    mode: str = "attention",
    top_n: int = 12,
    start: str | None = None,
    end: str | None = None,
    narratives: str | None = None,
):
    try:
        # If explicit narrative IDs are requested, bypass top_n filtering
        if narratives:
            df = get_timeline_df(DB_PATH)
            ids = [int(x) for x in narratives.split(",")]
            df = df[df["narrative_id"].isin(ids)].copy()
        else:
            df = get_timeline_with_other(DB_PATH, top_n=top_n, start=start, end=end)

        if df.empty:
            return []

        # Convert timestamps to strings for JSON serialization
        if hasattr(df["week_start"].dtype, "tz") or str(df["week_start"].dtype).startswith("datetime"):
            df["week_start"] = df["week_start"].dt.strftime("%Y-%m-%d")

        records = df.to_dict(orient="records")
        # Replace NaN with None for JSON serialization
        for rec in records:
            for k, v in rec.items():
                if isinstance(v, float) and v != v:  # NaN check
                    rec[k] = None
        return records
    except Exception as e:
        logger.error("Failed to get timeline: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/pipeline/run")
async def trigger_pipeline(background_tasks: BackgroundTasks):
    async with _pipeline_lock:
        if _pipeline_status["running"]:
            return {"status": "already_running"}
        _pipeline_status["running"] = True

    logger.info("Pipeline run triggered")
    background_tasks.add_task(_run_pipeline_task)
    return {"status": "started"}


@app.post("/api/pipeline/analyze")
async def trigger_analysis(background_tasks: BackgroundTasks):
    async with _pipeline_lock:
        if _pipeline_status["running"]:
            return {"status": "already_running"}
        _pipeline_status["running"] = True

    logger.info("Analysis run triggered")
    background_tasks.add_task(_run_analysis_task)
    return {"status": "started"}


@app.get("/api/pipeline/status")
def pipeline_status():
    return _pipeline_status


def _update_progress(step: int, label: str) -> None:
    _pipeline_status["step"] = step
    _pipeline_status["step_label"] = label


def _start_pipeline(total_steps: int) -> None:
    _pipeline_status["last_result"] = None
    _pipeline_status["step"] = 0
    _pipeline_status["total_steps"] = total_steps
    _pipeline_status["step_label"] = ""


def _finish_pipeline() -> None:
    _pipeline_status["running"] = False
    _pipeline_status["step"] = 0
    _pipeline_status["step_label"] = ""


def _run_pipeline_task():
    _start_pipeline(total_steps=11)
    try:
        from narratio.config import get_config
        from narratio.pipeline import run_pipeline
        from dataclasses import replace

        cfg = get_config()
        cfg = replace(cfg, db_path=DB_PATH)
        run_pipeline(
            cfg,
            progress_callback=_update_progress,
        )
        _pipeline_status["last_result"] = "success"
    except Exception as e:
        _pipeline_status["last_result"] = f"error: {e}"
    finally:
        _finish_pipeline()


def _run_analysis_task():
    _start_pipeline(total_steps=9)
    try:
        from narratio.config import get_config
        from narratio.pipeline import run_analysis
        from dataclasses import replace

        cfg = get_config()
        cfg = replace(cfg, db_path=DB_PATH)
        run_analysis(
            cfg,
            progress_callback=_update_progress,
        )
        _pipeline_status["last_result"] = "success"
    except Exception as e:
        _pipeline_status["last_result"] = f"error: {e}"
    finally:
        _finish_pipeline()
