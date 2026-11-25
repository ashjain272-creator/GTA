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
    assert {"ingest", "transcribe", "audio_analysis", "scene_detection", "audio_events", "candidates", "plan",
            "render", "qa"} <= names
    plan = json.loads((out / "plan.json").read_text())
    assert plan["style"]["selected_because"] and plan["framing"]["layout"] in {"tracked_crop", "blur_fill"}
    assert plan["contribution"], "edit should document its contributions"
    codes = {w["code"] for w in rep["warnings"]}
    assert "heuristic_ranker" in codes                              # limitations are surfaced
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


def test_l0_bundles_are_honest_and_platform_specific(demo, tmp_path):
    import json as _json
    from pathlib import Path

    from clipops import config
    from clipops.packaging.bundle import make_bundle
    from clipops.storage.artefacts import read_json

    _, s, out = demo
    cfg = config.load()
    src_dir = config.data_path(cfg, "work") / s["source_id"]
    plan = read_json(out / "plan.json")
    qa = read_json(out / "qa.json")
    info = read_json(next((src_dir / "renders").glob("*.json")))
    metas = {p: make_bundle(cfg, src_dir, plan, info, qa, p, tmp_path) for p in ("youtube", "tiktok", "instagram")}
    for p, m in metas.items():
        assert m["ready"] is False                                   # never ready without human and creative review
        assert {"human_review", "creative_review"} & set(m["verdict"]["blocking"])
        contrib_ok = next(c for c in m["verdict"]["checks"] if c["name"] == "contribution_test")["passed"]
        assert contrib_ok == (len(plan["contribution"]) >= 2)
        text = (tmp_path / info["short_id"] / p / "text.md").read_text()
        assert text.startswith("# NOT READY")
    assert metas["tiktok"]["watermark_allowed"] is False
    assert metas["youtube"]["flags"]["privacyStatus"] == "private"    # never rely on the public default (R33)
    ig = (tmp_path / info["short_id"] / "instagram" / "video.mp4").read_bytes()
    assert b"elst" not in ig and ig.find(b"moov") < ig.find(b"mdat")   # Reels spec: no edit lists, moov first


def test_gate_can_pass_when_every_requirement_is_met(demo, tmp_path):
    from clipops import config
    from clipops.packaging.bundle import load_profile
    from clipops.publish.gate import evaluate
    from clipops.storage.artefacts import read_json

    _, s, out = demo
    cfg = config.load()
    src_dir = config.data_path(cfg, "work") / s["source_id"]
    plan = read_json(out / "plan.json") | {"contribution": ["narrative restructuring", "commentary captions"]}
    info = read_json(next((src_dir / "renders").glob("*.json")))
    # QA record of the render as it is now (an earlier test re-rendered it; the gate must see a matching hash)
    qa = read_json(src_dir / "qa" / f"{info['short_id']}.json") | {"review_flags": [], "creative_review": "reviewed: rubric record R-1"}
    v = evaluate(cfg, src_dir, plan, info, qa, "youtube", load_profile(config.REPO, "youtube"))
    assert v["ready"], v["blocking"]
