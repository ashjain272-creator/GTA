"""Editing engine: style selection, smart framing, captions, punch-ins, effects, hooks, cold open."""
from __future__ import annotations

import copy
from pathlib import Path

import pytest

from clipops import config
from clipops.editing import framing as framing_mod
from clipops.editing.hooks import best_quote, make_hook
from clipops.editing.plan import make_plan, sfx_events
from clipops.editing.styles import select_style
from clipops.media import run
from clipops.render.subtitles import build_ass

REPO = Path(__file__).resolve().parents[2]
CFG = config.load(REPO)


def W(t, a, b, c=0.95):
    return {"text": t, "start_us": int(a * 1e6), "end_us": int(b * 1e6), "confidence": c}


STORY = [W("Okay,", 1.6, 1.9), W("watch", 2.0, 2.3), W("this.", 2.35, 2.7), W("I", 2.9, 3.0), W("am", 3.05, 3.2),
         W("going", 3.25, 3.5), W("to", 3.55, 3.6), W("jump", 3.65, 3.9), W("the", 3.95, 4.0), W("car.", 4.05, 4.4),
         W("Here", 7.0, 7.2), W("we", 7.25, 7.35), W("go.", 7.4, 7.7),
         W("No", 10.5, 10.7), W("way!", 10.75, 11.0), W("That", 11.1, 11.3), W("actually", 11.35, 11.7), W("worked.", 11.75, 12.2)]
TRANSCRIPT = {"segments": [{"start_us": 1_600_000, "end_us": 12_200_000, "text": "", "words": STORY}]}


def cand(impact=0.6, laugh=0.0):
    return {"candidate_id": "cand_0123abcd_00001000", "source_id": "src_0123abcd00000000", "version": 1,
            "boundaries": {"start_us": 1_000_000, "end_us": 14_000_000},
            "scores": {"hook": {"value": 0.6}, "emotional_intensity": {"value": 0.7}},
            "signals": {"payoff_us": 9_750_000, "impact_score": impact, "laughter": laugh, "exclamations": 2,
                        "reaction": 1.0, "setup_present": True},
            "transcript_excerpt": "Okay, watch this. I am going to jump the car."}


def prof(**k):
    base = {"energy": 0.5, "humor": 0.3, "dialogue": 0.5, "impact": 0.3, "calm": 0.5}
    return base | k


def test_style_choice_follows_the_moment_not_rotation():
    assert select_style(REPO, CFG, prof(energy=0.9, impact=0.95, humor=0.1, dialogue=0.2, calm=0.1), recent=[])["name"] == "high_energy"
    assert select_style(REPO, CFG, prof(energy=0.7, humor=0.9, dialogue=0.9, impact=0.1, calm=0.3), recent=[])["name"] == "funny_chaotic"
    calm = select_style(REPO, CFG, prof(energy=0.1, humor=0.0, dialogue=0.8, impact=0.0, calm=0.9), recent=[])["name"]
    assert calm in {"clean_minimal", "documentary", "cinematic"}


def test_unavailable_styles_are_excluded_with_reasons_and_overuse_is_penalised():
    sel = select_style(REPO, CFG, prof(energy=0.9, impact=0.95), recent=[])
    excluded = {e["style"] for e in sel["excluded"]}
    assert {"meme_reaction", "commentary_overlay"} <= excluded
    assert sel["selected_because"] and sel["runner_up"]
    over = select_style(REPO, CFG, prof(energy=0.9, impact=0.95, humor=0.1, dialogue=0.2, calm=0.1),
                        recent=["high_energy"] * 10)
    assert any("overuse" in r for row in over["all_scores"] if row["style"] == "high_energy" for r in row["reasons"])


def _plan(style_name, framing=None):
    sel = select_style(REPO, CFG, prof(), recent=[], force=style_name)
    fr = framing or {"layout": "tracked_crop", "subject_y": 0.3, "keyframes": [], "reason": "test"}
    return make_plan(cand(), TRANSCRIPT, CFG, style_sel=sel, framing=fr, game="Grand Theft Auto V")


def test_cold_open_teases_the_payoff_without_cutting_words():
    p = _plan("high_energy")
    teaser = p["timeline"][0]
    assert teaser["role"] == "teaser"
    for w in STORY:
        for edge in (teaser["src_start_us"], teaser["src_end_us"]):
            assert not (w["start_us"] < edge < w["end_us"]), f"teaser edge cuts '{w['text']}'"
    assert any(c["type"] == "editorial_restructuring" for c in p["contribution"])


def test_speed_ramp_never_slows_speech():
    p = _plan("high_energy")
    for s in p["timeline"]:
        if s["role"] == "ramp":
            assert not any(w["start_us"] < s["src_end_us"] and w["end_us"] > s["src_start_us"] for w in STORY)


def test_effects_respect_style_limits_speech_and_no_stacking():
    for st in ("funny_chaotic", "high_energy", "cinematic"):
        p = _plan(st)
        times = sorted(e["out_us"] for e in p["sfx"])
        assert all(b - a >= 350_000 for a, b in zip(times, times[1:]))
        limit = max(1, int(p["duration_us"] / 10e6 * select_style(REPO, CFG, prof(), recent=[], force=st)["params"]["sfx"]["max_per_10s"] + 0.5))
        assert len(p["sfx"]) <= limit
    assert _plan("clean_minimal")["sfx"] == [] and _plan("clean_minimal")["zooms"] == []


def test_punch_ins_are_capped_and_spaced():
    p = _plan("funny_chaotic")
    z = p["zooms"]
    assert 1 <= len(z) <= max(1, int(p["duration_us"] / 10e6 * 3 + 0.5))
    assert all(b["anchor_us"] - a["anchor_us"] >= 1_200_000 for a, b in zip(z, z[1:]))
    assert all(1.0 < x["scale"] <= 1.30 for x in z)


def test_hook_uses_verbatim_words_only():
    q = best_quote(STORY, 9_750_000)
    assert q["text"] in " ".join(w["text"] for w in STORY)
    h = make_hook("context", STORY, 9_750_000, "Grand Theft Auto V")
    assert h["text"].startswith("Grand Theft Auto V") and "going to jump" in h["text"]


def test_captions_move_away_from_a_low_subject():
    low = _plan("funny_chaotic", {"layout": "tracked_crop", "subject_y": 0.66, "keyframes": [], "reason": "t"})
    high = _plan("funny_chaotic", {"layout": "tracked_crop", "subject_y": 0.25, "keyframes": [], "reason": "t"})
    assert low["subtitles"]["style"].get("alignment") == 8 and "upper band" in low["subtitles"]["placement"]
    assert high["subtitles"]["placement"] == "bottom"


def test_animated_ass_contains_style_specific_tags():
    p = _plan("funny_chaotic")
    ass = build_ass(p["subtitles"]["cues"], 1080, 1920, p["subtitles"]["style"], p["hook"])
    assert "\\t(0,70,\\fscx118" in ass and "Style: Hook" in ass
    k = _plan("high_energy")
    assert "\\kf" in build_ass(k["subtitles"]["cues"], 1080, 1920, k["subtitles"]["style"], k["hook"])


@pytest.mark.media
def test_tracker_follows_a_moving_subject(tmp_path):
    src = tmp_path / "mov.mp4"
    run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=0x404040:s=1280x720:r=30:d=6",
         "-f", "lavfi", "-i", "color=c=yellow:s=120x80:r=30:d=6",
         "-filter_complex", "[0][1]overlay=x='60+t*180':y=300:shortest=1", "-c:v", "libx264", "-qp", "0", str(src)])
    fr = framing_mod.track(src, 0, 6, 1280, 720, CFG)
    assert fr["layout"] == "tracked_crop"
    early, late = fr["keyframes"][10]["cx"], fr["keyframes"][-5]["cx"]
    assert late - early > 0.35, (early, late)              # crop moved right with the subject
    box_x = (60 + 5.5 * 180 + 60) / 1280                    # subject centre near the end
    assert abs(late - box_x) < fr["window_fraction"] / 2    # subject inside the crop window


@pytest.mark.media
def test_first_person_crop_stays_on_the_crosshair(tmp_path):
    src = tmp_path / "fp.mp4"
    run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=0x404040:s=1280x720:r=30:d=4",
         "-f", "lavfi", "-i", "color=c=yellow:s=120x80:r=30:d=4",
         "-filter_complex", "[0][1]overlay=x='60+t*250':y=300:shortest=1", "-c:v", "libx264", "-qp", "0", str(src)])
    fr = framing_mod.track(src, 0, 4, 1280, 720, CFG, camera="first_person")
    assert fr["layout"] == "tracked_crop" and "crosshair" in fr["reason"]
    assert all(abs(k["cx"] - 0.5) < 1e-6 for k in fr["keyframes"])


@pytest.mark.media
def test_flash_mitigation_is_chosen_for_a_flashing_window(tmp_path):
    from clipops.qa.window_checks import source_flash_risk
    src = tmp_path / "flash.mp4"
    run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=black:s=320x180:r=30:d=3", "-vf",
         "geq=lum='if(lt(mod(T*8,1),0.5),235,16)':cb=128:cr=128,format=yuv420p", "-c:v", "libx264", "-qp", "0", str(src)])
    r = source_flash_risk(src, 0, 3, CFG)
    assert r["risk"] and r["mitigation"] and r["mitigation"]["threshold"] <= 0.5
