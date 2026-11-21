"""Edit plan (spec A.2), skeleton grade.

There is no style engine yet (Phase 5). The plan says so in `selected_because`
instead of pretending a style was chosen on merit (spec 1.8 #3).
"""
from __future__ import annotations

import re

_PUNCT_END = re.compile(r"[.!?,;:]$")


def make_plan(candidate: dict, transcript: dict, cfg: dict) -> dict:
    b = candidate["boundaries"]
    cues = subtitle_cues(transcript, b["start_us"], b["end_us"], cfg["render"]["subtitles"])
    return {
        "plan_id": f"plan_{candidate['candidate_id'][5:]}_v{candidate['version']}",
        "candidate_id": candidate["candidate_id"],
        "source_id": candidate["source_id"],
        "version": 1,
        "intent": f"Present the moment: \"{candidate['transcript_excerpt'][:80]}\"",
        "style": {"name": "skeleton-plain", "parameters": {},
                  "selected_because": ["walking skeleton: style engine not built yet (Phase 5); "
                                       "this is the only style available, so no selection was made"],
                  "runner_up": None, "runner_up_reason": None},
        "structure": {"name": "linear_build"},
        "timeline": [{"type": "source_segment", "src_start_us": b["start_us"], "src_end_us": b["end_us"],
                      "speed": 1.0}],
        "layout": {"name": "blur_fill_center", "reason": "no subject tracking yet; full frame kept visible"},
        "subtitles": {"cues": cues, "style": dict(cfg["render"]["subtitles"])},
        "audio": {"loudness_target_lufs": cfg["render"]["loudness_target_lufs"],
                  "true_peak_dbtp": cfg["render"]["true_peak_dbtp"], "music": None, "sfx": []},
        "duration_us": b["end_us"] - b["start_us"],
        "contribution": [],
        "contribution_note": "none yet: skeleton output is not publishable (fails spec 4.7 contribution test)",
    }


def subtitle_cues(transcript: dict, start_us: int, end_us: int, scfg: dict) -> list[dict]:
    """Group words into short cues, timed relative to the clip start. Never splits a word."""
    words = [w for s in transcript.get("segments", []) for w in s["words"]
             if w["start_us"] >= start_us and w["end_us"] <= end_us]
    cues: list[dict] = []
    cur: list[dict] = []
    max_w, max_us = scfg["max_words_per_cue"], int(scfg["max_cue_s"] * 1e6)

    def flush():
        if cur:
            cues.append({"start_us": cur[0]["start_us"] - start_us, "end_us": cur[-1]["end_us"] - start_us,
                         "text": " ".join(w["text"] for w in cur),
                         "min_confidence": min(w["confidence"] for w in cur)})
            cur.clear()

    for w in words:
        if cur and (len(cur) >= max_w or w["end_us"] - cur[0]["start_us"] > max_us
                    or w["start_us"] - cur[-1]["end_us"] > 700_000):
            flush()
        cur.append(w)
        if _PUNCT_END.search(w["text"]):
            flush()
    flush()
    # close tiny gaps so captions don't flicker; never overlap the next cue
    for a, b in zip(cues, cues[1:]):
        if 0 < b["start_us"] - a["end_us"] < 250_000:
            a["end_us"] = b["start_us"]
    return cues
