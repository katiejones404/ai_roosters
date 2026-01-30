from __future__ import annotations

from app.services.sentiment.article_processing import (
    IngestArtifact,
    _is_cuda_related_error,
    finbert_articles,
    scores_dict,
    select_device,
)


def test_scores_dict_fills_missing_labels():
    d = scores_dict(
        [
            {"label": "POSITIVE", "score": 0.8},
            {"label": "NEGATIVE", "score": 0.1},
        ]
    )
    assert d["positive"] == 0.8
    assert d["negative"] == 0.1
    assert d["neutral"] == 0.0


def test_finbert_articles_with_no_descriptions_skips_model_load():
    artifact = IngestArtifact(
        published_at=[],
        title=[],
        description=[],
        url=[],
    )
    out = finbert_articles(artifact)
    assert out.sentiment == []
    assert out.sentiment_score == []
    assert out.prob_pos == []
    assert out.prob_neg == []
    assert out.prob_neu == []


def test_select_device_force_cpu_env_var(monkeypatch):
    monkeypatch.setenv("FINBERT_FORCE_CPU", "1")
    assert select_device() == -1


def test_is_cuda_related_error_detection():
    assert _is_cuda_related_error(RuntimeError("CUDA out of memory")) is True
    assert _is_cuda_related_error(RuntimeError("some other error")) is False
