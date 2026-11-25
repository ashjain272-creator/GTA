from __future__ import annotations

import copy
from pathlib import Path

import pytest

from clipops import config
from clipops.candidates.generate import _blocks, generate
from clipops.editing.plan import subtitle_cues
from clipops.qa.wer import wer
from clipops.render.subtitles import _ts, build_ass

CFG = config.load(Path(__file__).resolve().parents[2])


def W(text, s, e, conf=0.9):
    return {"text": text, "start_us": int(s * 1e6), "end_us": int(e * 1e6), "confidence": conf}


def transcript(words):
    # one segment spanning everything, as Whisper sometimes produces
    return {"segments": [{"start_us": words[0]["start_us"], "end_us": words[-1]["end_us"],
                          "text": " ".join(w["text"] for w in words), "words": words}]}


def test_blocks_split_on_word_gaps_even_inside_one_segment():
    t = transcript([W("a", 0, 0.5), W("b", 0.6, 1.0), W("c", 5.0, 5.4)])
    blocks = _blocks(t["segments"])
    assert [b["text"] for b in blocks] == ["a b", "c"]


CLEAN = {"frames": [], "unscreened": False}


def _gen(words, curve=None, ovr_events=CLEAN, **ovr):
    cfg = copy.deepcopy(CFG)
    cfg["candidates"].update(ovr)
    curve = curve or [(i / 10, -20.0) for i in range(0, 600)]
    return generate("src_0123456789abcdef", 60_000_000, transcript(words), curve, [],
                    {"p50_lufs": -25.0}, {"class": "A"}, cfg, events=ovr_events)


def test_candidate_boundaries_never_cut_inside_a_word():
    words = [W(f"w{i}", i * 0.5, i * 0.5 + 0.4) for i in range(30)]
    res = _gen(words)
    starts = {w["start_us"] for w in words}
    ends = {w["end_us"] for w in words}
    lead, tail = int(CFG["candidates"]["lead_in_s"] * 1e6), int(CFG["candidates"]["tail_s"] * 1e6)
    for c in res["candidates"]:
        b = c["boundaries"]
        assert max(0, min(starts) - lead) <= b["start_us"]
        assert b["start_us"] + lead in starts or b["start_us"] == 0
        assert b["end_us"] - tail in ends


def test_short_and_dead_air_windows_are_rejected_with_reasons():
    words = [W("hi", 1, 1.5), W("there", 1.6, 2.0),            # 1 s block: too short alone
             W("x", 3.0, 3.3), W("y", 9.0, 9.4)]                  # 5.7 s pause inside the merged window
    res = _gen(words, min_duration_s=8.0, max_internal_gap_s=3.0)
    rejected = [c for c in res["candidates"] if c["status"] == "rejected"]
    assert rejected and all(c["rejection_reason"] for c in rejected)
    reasons = " ".join(c["rejection_reason"] for c in rejected)
    assert "duration" in reasons or "dead_air" in reasons


def test_overlapping_candidates_are_deduplicated():
    words = [W(f"w{i}", i * 0.5, i * 0.5 + 0.4) for i in range(60)]
    res = _gen(words, max_candidates_per_source=10, min_viability=0.0)
    kept = [c for c in res["candidates"] if c["status"] == "proposed"]
    for i, a in enumerate(kept):
        for b in kept[i + 1:]:
            s = max(a["boundaries"]["start_us"], b["boundaries"]["start_us"])
            e = min(a["boundaries"]["end_us"], b["boundaries"]["end_us"])
            shorter = min(a["boundaries"]["end_us"] - a["boundaries"]["start_us"],
                          b["boundaries"]["end_us"] - b["boundaries"]["start_us"])
            assert max(0, e - s) / shorter <= 0.5


def test_subtitle_cues_respect_limits_and_never_overlap():
    words = [W("Okay,", 1.0, 1.3), W("watch", 1.4, 1.7), W("this.", 1.8, 2.1)] + \
            [W(f"word{i}", 2.2 + i * 0.3, 2.4 + i * 0.3) for i in range(12)]
    cues = subtitle_cues(transcript(words), 500_000, 10_000_000, CFG["render"]["subtitles"])
    assert cues[0]["text"] == "Okay,"                       # breaks at punctuation
    assert all(len(c["text"].split()) <= CFG["render"]["subtitles"]["max_words_per_cue"] for c in cues)
    assert all(a["end_us"] <= b["start_us"] for a, b in zip(cues, cues[1:]))
    assert cues[0]["start_us"] == 500_000                   # relative to the clip start
    assert " ".join(c["text"] for c in cues).split() == [w["text"] for w in words]


def test_ass_timestamps_and_escaping():
    assert _ts(0) == "0:00:00.00"
    assert _ts(61_234_567) == "0:01:01.23"
    ass = build_ass([{"start_us": 0, "end_us": 1_000_000, "text": "a {b} \\c"}], 1080, 1920,
                    CFG["render"]["subtitles"])
    assert "PlayResY: 1920" in ass
    assert "{b}" not in ass.split("[Events]")[1]


def test_wer():
    assert wer("No way, that worked!", "no way that worked")["wer"] == 0.0
    assert wer("a b c d", "a x c")["errors"] == 2


def test_music_gate_rejects_music_and_fails_closed_when_unscreened():
    words = [W(f"w{i}", i * 0.5, i * 0.5 + 0.4) for i in range(30)]
    music = {"unscreened": False, "frames": [{"t_us": int(t * 1e6), "music": 0.9} for t in range(0, 20)]}
    res = _gen(words, ovr_events=music)
    assert all(c["status"] == "rejected" and "music_screen" in c["rejection_reason"] for c in res["candidates"])
    res = _gen(words, ovr_events={"frames": [], "unscreened": True})
    assert all("not screened" in c["rejection_reason"] for c in res["candidates"])
    res = _gen(words, min_viability=0.0)                # screened, no music: the gate itself passes
    assert all(g["passed"] for c in res["candidates"] for g in c["gates"] if g["name"] == "music_screen")


def test_impact_followed_by_reaction_outranks_flat_speech():
    flat = [W(f"word{i}", 1 + i * 0.5, 1 + i * 0.5 + 0.4) for i in range(20)]
    story = [W("Watch", 21.0, 21.3), W("this.", 21.4, 21.7), W("I", 22, 22.1), W("am", 22.2, 22.3),
             W("going", 22.4, 22.6), W("to", 22.7, 22.8), W("jump.", 22.9, 23.3),
             W("No", 26.2, 26.4), W("way!", 26.5, 26.9), W("That", 27, 27.2), W("worked!", 27.3, 27.8),
             W("Best", 28.5, 28.8), W("jump", 28.9, 29.2), W("ever.", 29.3, 29.7)]
    ev = {"unscreened": False, "frames": [{"t_us": int(t * 1e6), "music": 0.0, "speech": 0.6,
                                           "explosion": 0.6 if 25.5 <= t <= 26.0 else 0.0}
                                          for t in [x * 0.5 for x in range(0, 80)]]}
    curve = [(t / 10, -40.0 if not 255 <= t <= 262 else -12.0) for t in range(600)]
    res = _gen(flat + story, curve=curve, ovr_events=ev, min_viability=0.0, max_candidates_per_source=10)
    ranked = [c for c in res["candidates"] if c["status"] == "proposed"]
    top = ranked[0]
    assert top["boundaries"]["start_us"] >= 20_000_000, [c["boundaries"] for c in ranked]
    assert top["signals"]["impact_score"] >= 0.5 and top["signals"]["reaction"] > 0
    assert top["signals"]["setup_present"] is True


def test_action_without_speech_becomes_a_candidate():
    ev = {"unscreened": False, "frames": [{"t_us": int(t * 1e6), "music": 0.0, "speech": 0.0,
                                           "gunshot": 0.7 if 30 <= t <= 33 else 0.0} for t in [x * 0.5 for x in range(0, 120)]]}
    curve = [(t / 10, -18.0 if 290 <= t <= 340 else -30.0) for t in range(600)]
    res = _gen([W("hello", 1, 1.3), W("there.", 1.4, 1.8)], curve=curve, ovr_events=ev, min_viability=0.0)
    event = [c for c in res["candidates"] if c["seed"]["pattern"] == "event_cluster"]
    assert event, "gunfire with no speech must still produce a candidate"
    b = event[0]["boundaries"]
    assert b["start_us"] <= 30_000_000 <= b["end_us"]


def test_clips_start_and_end_on_sentence_boundaries():
    words = ([W("the", 0.5, 0.7), W("end.", 0.8, 1.1)] +
             [W(x, 3 + i * 0.4, 3.3 + i * 0.4) for i, x in enumerate("So here is my plan for the bridge.".split())] +
             [W(x, 7 + i * 0.4, 7.3 + i * 0.4) for i, x in enumerate("Watch me jump it now and".split())] +
             [W(x, 10 + i * 0.4, 10.3 + i * 0.4) for i, x in enumerate("then we celebrate.".split())])
    res = _gen(words, min_viability=0.0, max_candidates_per_source=10)
    for c in res["candidates"]:
        first = c["transcript_excerpt"].split()[0]
        assert first[0].isupper() or first in ("the",) and False, c["transcript_excerpt"]
        assert c["transcript_excerpt"].rstrip()[-1] in ".!?", c["transcript_excerpt"]


def test_licence_covered_music_passes_gate():
    words = [W(f"w{i}", i * 0.5, i * 0.5 + 0.4) for i in range(30)]
    music = {"unscreened": False, "frames": [{"t_us": int(t * 1e6), "music": 0.9} for t in range(0, 20)]}
    cfg = copy.deepcopy(CFG)
    res = generate("src_0123456789abcdef", 60_000_000, transcript(words), [(i / 10, -20.0) for i in range(600)], [],
                   {"p50_lufs": -25.0}, {"class": "C", "grant": {"document_ref": "cc-by", "covers_audio": True}}, cfg, events=music)
    gates = [g for c in res["candidates"] for g in c["gates"] if g["name"] == "music_screen"]
    assert gates and all(g["passed"] and "covered by the source licence" in g["reason"] for g in gates)


@pytest.mark.smoke
def test_event_window_end_lands_in_a_pause_not_mid_sentence():
    from clipops.candidates.generate import _speech_safe_end, _speech_safe_start
    t = [(10.0, 10.4), (10.4, 10.8), (10.8, 11.6), (13.2, 13.5), (13.5, 13.8), (13.8, 14.2), (14.2, 14.6)]
    words = [{"text": "w", "start_us": int(a * 1e6), "end_us": int(b * 1e6)} for a, b in t]
    b = _speech_safe_end(words, 14_000_000, lo=8_000_000, hi=30_000_000)
    assert 11_600_000 < b < 13_200_000                     # back to the 1.6 s pause, not into "when the world..."
    a = _speech_safe_start(words, 13_600_000, lo=10_000_000, hi=14_000_000)
    assert 11_600_000 < a <= 13_200_000
    assert _speech_safe_end(words, 20_000_000, lo=0, hi=30_000_000) == 20_000_000   # silence: unchanged


@pytest.mark.smoke
def test_cross_verify_drops_refine_hallucinations_in_silence():
    from clipops.analysis.transcribe import cross_verify
    base = [W("okay", 1.0, 1.3), W("go", 1.4, 1.6)]
    refined = [W("Okay,", 1.0, 1.3), W("go.", 1.4, 1.6), W("I", 9.0, 9.2), W("don't", 9.2, 9.5), W("know.", 9.5, 9.9)]
    out = cross_verify(base, refined)
    assert [w["text"] for w in out] == ["Okay,", "go."] and all(w["verified"] for w in out)
