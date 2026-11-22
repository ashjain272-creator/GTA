"""End-to-end walking skeleton on the synthetic fixture (Appendix I step 9).

Asserts real measured outcomes; skips only when a declared prerequisite is absent.
"""
from __future__ import annotations

import json
import shutil

import pytest

pytestmark = [pytest.mark.slow, pytest.mark.media]


@pytest.fixture(scope="module")
def demo(tmp_path_factory):
    if not shutil.which("espeak-ng"):
        pytest.skip("espeak-ng not installed (needed to synthesise fixture speech)")
    pytest.importorskip("faster_whisper")
    from clipops import config
    from clipops.demo import run_demo
    out = tmp_path_factory.mktemp("demo")
    code = run_demo(config.load(), out)
    return code, json.loads((out / "summary.json").read_text()), out


def test_demo_exit_and_qa(demo):
    code, s, _ = demo
    assert code == 0, s
    assert s["qa_passed"] is True
    assert s["qa_failed"] == []


def test_transcription_accuracy_on_synthetic_speech(demo):
    _, s, _ = demo
    assert s["wer"]["wer"] <= 0.10, s["wer"]


def test_top_candidate_covers_the_planted_moment(demo):
    _, s, _ = demo
    assert s["top_candidate"]["covers_expected_moment"], s["top_candidate"]


def test_run_report_lists_every_stage_and_warning(demo):
    _, s, out = demo
    rep = json.loads((out / s["run_report"]).read_text())
    names = {st["name"] for st in rep["stages"]}
    assert {"ingest", "transcribe", "audio_analysis", "scene_detection", "candidates", "plan",
            "render", "qa"} <= names
    codes = {w["code"] for w in rep["warnings"]}
    assert {"heuristic_ranker", "no_style_engine"} <= codes        # limitations are surfaced
    assert all(a["sha256"] for a in rep["artefacts"])


def test_rerun_after_interruption_resumes_from_artefacts(demo, monkeypatch):
    """Recovery (DoD #8): a render that crashes mid-run leaves analysis reusable;
    the next run resumes from cached artefacts and completes."""
    from clipops import config
    from clipops.orchestrator import pipeline as pl
    from clipops.runreport import RunReport, StageFailed
    _, s, _ = demo
    cfg = config.load()

    def crash(*a, **k):
        raise StageFailed("injected", "transient", "simulated power loss during render")
    monkeypatch.setattr(pl, "render", crash)
    rep = RunReport(cfg, "interrupted")
    p = pl.Pipeline(cfg, rep)
    plan = p.plan(s["source_id"])
    with pytest.raises(StageFailed):
        p.render_and_qa(s["source_id"], plan)
    monkeypatch.undo()

    rep2 = RunReport(cfg, "resumed")
    p2 = pl.Pipeline(cfg, rep2)
    info, qa = p2.render_and_qa(s["source_id"], p2.plan(s["source_id"]))
    status = {st["name"]: st["status"] for st in rep2.data["stages"]}
    assert status["transcribe"] == "cached" and status["candidates"] == "cached"
    assert qa["passed"]


def test_music_bed_blocks_every_candidate(tmp_path):
    """R26 end to end: speech over a music bed yields no publishable candidate."""
    import subprocess
    import sys
    from pathlib import Path

    from clipops import config
    from clipops.orchestrator.pipeline import Pipeline
    from clipops.runreport import RunReport, StageFailed

    repo = Path(__file__).resolve().parents[2]
    fx = tmp_path / "music_fixture.mp4"
    subprocess.run([sys.executable, str(repo / "scripts" / "make_synthetic_fixture.py"), str(fx), "--music"],
                   check=True, capture_output=True)
    cfg = config.load(overrides={"paths": {"work": str(tmp_path / "work"), "renders": str(tmp_path / "renders")}})
    p = Pipeline(cfg, RunReport(cfg, "music test"))
    sid = p.add_source(fx, "A", game=None, grant=None, synthetic=True)
    cands = p.candidates(sid)["candidates"]
    assert cands and all(c["status"] == "rejected" for c in cands)
    assert all("music_screen" in c["rejection_reason"] for c in cands)
    with pytest.raises(StageFailed, match="no proposed candidate"):
        p.plan(sid)
