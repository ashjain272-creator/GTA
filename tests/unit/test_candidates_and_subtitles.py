from __future__ import annotations

import copy
from pathlib import Path

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


def _gen(words, curve=None, **ovr):
    cfg = copy.deepcopy(CFG)
    cfg["candidates"].update(ovr)
    curve = curve or [(i / 10, -20.0) for i in range(0, 600)]
    return generate("src_0123456789abcdef", 60_000_000, transcript(words), curve, [],
                    {"p50_lufs": -25.0}, {"class": "A"}, cfg)


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
    res = _gen(words, max_candidates_per_source=10)
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
