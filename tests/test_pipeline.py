"""Tests for the pipeline orchestrator."""

from unittest.mock import patch, MagicMock
from narratio.pipeline import run_pipeline


def test_run_pipeline_calls_stages_in_order(tmp_path):
    db_path = str(tmp_path / "test.db")
    emb_path = str(tmp_path / "embeddings.npy")

    call_order = []

    with (
        patch("narratio.pipeline.init_db") as mock_init,
        patch("narratio.pipeline.ingest_articles", return_value=100) as mock_ingest,
        patch("narratio.pipeline.embed_articles", return_value=100) as mock_embed,
        patch("narratio.pipeline.cluster_articles", return_value=5) as mock_cluster,
        patch("narratio.pipeline.analyze_sentiment", return_value=100) as mock_sentiment,
        patch("narratio.pipeline.label_clusters", return_value=5) as mock_label,
        patch("narratio.pipeline.summarize_narratives", return_value=10) as mock_summarize,
        patch("narratio.pipeline.generate_report", return_value="report output") as mock_report,
        patch("narratio.pipeline.finnhub") as mock_finnhub,
        patch("narratio.pipeline._ensure_analysis_rows") as mock_ensure,
    ):
        mock_init.side_effect = lambda *a: call_order.append("init_db")
        mock_ingest.side_effect = lambda *a, **kw: (call_order.append("ingest"), 100)[1]
        mock_embed.side_effect = lambda *a, **kw: (call_order.append("embed"), 100)[1]
        mock_cluster.side_effect = lambda *a, **kw: (call_order.append("cluster"), 5)[1]
        mock_sentiment.side_effect = lambda *a, **kw: (call_order.append("sentiment"), 100)[1]
        mock_label.side_effect = lambda *a, **kw: (call_order.append("label"), 5)[1]
        mock_summarize.side_effect = lambda *a, **kw: (call_order.append("summarize"), 10)[1]
        mock_report.side_effect = lambda *a: (call_order.append("report"), "output")[1]

        run_pipeline(
            finnhub_key="test-key",
            openrouter_key="test-key",
            db_path=db_path,
            embeddings_path=emb_path,
        )

    assert call_order == [
        "init_db",
        "ingest",
        "embed",
        "cluster",
        "sentiment",
        "label",
        "summarize",
        "report",
    ]
