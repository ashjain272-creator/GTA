"""Resumability (spec 1.3 P9): cache keys include stage versions and config."""
from __future__ import annotations

from clipops.orchestrator import pipeline


def test_key_changes_with_stage_version_and_config(monkeypatch):
    k1 = pipeline._key("cands", 1, {"a": 1})
    assert k1 != pipeline._key("cands", 2, {"a": 1})
    assert k1 != pipeline._key("cands", 1, {"a": 2})
    assert k1 == pipeline._key("cands", 1, {"a": 1})


def test_cached_requires_matching_key(tmp_path):
    p = tmp_path / "x.json"
    pipeline._store(p, "k1", {"v": 1})
    assert pipeline._cached(p, "k1") == {"v": 1, "_input_key": "k1"}
    assert pipeline._cached(p, "k2") is None
