"""Candidate generation and crude ranking (spec 7.3-7.8), walking-skeleton grade.

Honesty note: the scoring here is an unvalidated heuristic (model_version
"skeleton-heuristic-2"). Its uncertainty is reported high on purpose. It exists
to exercise the candidate schema, gates and rejection records end to end, not
to claim it finds good moments. The Phase 4 ranker replaces it.
"""
from __future__ import annotations

import bisect
import re

MODEL_VERSION = "skeleton-heuristic-3"
EXCLAIM = re.compile(r"\b(no way|oh my|wow|what|let'?s go|yes|no no|insane|holy)\b|!", re.I)


def _blocks(segments: list[dict], max_gap_us: int = 1_500_000) -> list[dict]:
    """Group words into utterance blocks split at pauses longer than max_gap_us.

    Word timestamps are used, not segment timestamps: Whisper-style segments can
    span long silences (observed in the walking skeleton, 2026-11-21).
    """
    blocks: list[dict] = []
    for w in (w for s in segments for w in s["words"]):
        if blocks and w["start_us"] - blocks[-1]["end_us"] <= max_gap_us:
            blocks[-1]["end_us"] = w["end_us"]
            blocks[-1]["words"].append(w)
        else:
            blocks.append({"start_us": w["start_us"], "end_us": w["end_us"], "words": [w]})
    for b in blocks:
        b["text"] = " ".join(w["text"] for w in b["words"])
    return blocks


def _window_pairs(curve: list[tuple[float, float]], times: list[float], a: float, b: float) -> list[tuple[float, float]]:
    i, j = bisect.bisect_left(times, a), bisect.bisect_right(times, b)
    return curve[i:j]


def _clip(x: float) -> float:
    return max(0.0, min(1.0, x))


def generate(source_id: str, duration_us: int, transcript: dict, curve: list[tuple[float, float]],
             scenes: list[dict], audio_summary: dict, rights: dict, cfg: dict,
             events: dict | None = None) -> dict:
    c = cfg["candidates"]
    lead, tail = int(c["lead_in_s"] * 1e6), int(c["tail_s"] * 1e6)
    min_d, max_d = int(c["min_duration_s"] * 1e6), int(c["max_duration_s"] * 1e6)
    blocks = _blocks(transcript.get("segments", []))
    times = [t for t, _ in curve]
    base = audio_summary.get("p50_lufs", -30.0)
    cut_times = [s["time_us"] for s in scenes]

    proposals = []
    for i in range(len(blocks)):
        # extend over following blocks until the minimum duration is met
        j = i
        while blocks[j]["end_us"] - blocks[i]["start_us"] < min_d and j + 1 < len(blocks) \
                and blocks[j + 1]["end_us"] - blocks[i]["start_us"] <= max_d:
            j += 1
        start = max(0, blocks[i]["start_us"] - lead)
        end = min(duration_us, blocks[j]["end_us"] + tail)
        if end - start > max_d:
            continue
        proposals.append((start, end, blocks[i:j + 1]))

    cands = []
    for start, end, blks in proposals:
        words = [w for b in blks for w in b["words"]]
        text = " ".join(b["text"] for b in blks)
        dur_s = (end - start) / 1e6
        pairs = _window_pairs(curve, times, start / 1e6, end / 1e6)
        loud = [m for _, m in pairs]
        peak_t, peak = max(pairs, key=lambda tm: tm[1]) if pairs else (start / 1e6, -120.0)
        rel_peak_pos = (peak_t - start / 1e6) / max(dur_s, 1e-6)
        intensity = _clip((peak - base) / 15.0)
        density = _clip(len(words) / dur_s / 3.5)
        exclaims = len(EXCLAIM.findall(text))
        first_words = " ".join(w["text"] for w in blks[0]["words"][:8])
        hook = _clip(0.5 * density + 0.5 * _clip(len(EXCLAIM.findall(first_words)) / 1.0))
        payoff = _clip(intensity * (1.0 if rel_peak_pos >= 0.4 else 0.5) + 0.2 * _clip(exclaims / 2))
        n_cuts = sum(1 for t in cut_times if start <= t <= end)
        visual = _clip(n_cuts / max(dur_s / 4, 1))
        mean_conf = sum(w["confidence"] for w in words) / len(words) if words else 0.0
        viability = round(0.30 * payoff + 0.25 * hook + 0.20 * intensity + 0.15 * density + 0.10 * visual, 4)
        window_p50 = sorted(loud)[len(loud) // 2] if loud else -120.0
        gaps = [(b["start_us"] - a["end_us"]) / 1e6 for a, b in zip(words, words[1:])]
        max_gap = max(gaps, default=0.0)
        gates = [
            {"name": "rights", "passed": True, "reason": f"class {rights['class']} record valid"},
            {"name": "audio_floor", "passed": window_p50 > -50.0,
             "reason": f"window median momentary loudness {window_p50:.1f} LUFS (floor -50)"},
            {"name": "duration", "passed": min_d <= end - start <= max_d,
             "reason": f"{dur_s:.1f}s vs allowed {c['min_duration_s']}-{c['max_duration_s']}s"},
            _music_gate(events, start, end, cfg["analysis"]),
            {"name": "dead_air", "passed": max_gap <= c["max_internal_gap_s"],
             "reason": f"longest pause between words {max_gap:.1f}s (max {c['max_internal_gap_s']}s)"},
            {"name": "payoff_floor", "passed": viability >= c["min_viability"],
             "reason": f"viability {viability:.2f} vs min {c['min_viability']}"},
        ]
        cands.append({
            "candidate_id": f"cand_{source_id[4:12]}_{start // 1000:08d}",
            "source_id": source_id, "version": 1,
            "seed": {"type": "coverage", "pattern": "utterance_block", "moment_ids": []},
            "boundaries": {"start_us": start, "end_us": end, "time_base": "us",
                           "variants_considered": 1,
                           "rules": ["start lead-in before first word", "end after reaction tail",
                                     "never inside a word (block boundaries)"]},
            "scores": {
                "hook": {"value": round(hook, 3), "confidence": 0.2, "evidence": [first_words]},
                "payoff": {"value": round(payoff, 3), "confidence": 0.2,
                           "evidence": [f"loudness peak {peak:.1f} LUFS at {peak_t:.2f}s ({rel_peak_pos:.0%} into clip)"]},
                "emotional_intensity": {"value": round(intensity, 3), "confidence": 0.3},
                "pacing": {"value": round(density, 3), "confidence": 0.3, "evidence": [f"{len(words)} words in {dur_s:.1f}s"]},
                "visual_interest": {"value": round(visual, 3), "confidence": 0.2, "evidence": [f"{n_cuts} scene cuts"]},
                "audio_quality": {"value": round(mean_conf, 3), "confidence": 0.3,
                                  "evidence": ["mean ASR word confidence used as intelligibility proxy"]},
                "standalone_context": {"verdict": "unassessed", "context_cost_s": None},
            },
            "overall": {"viability": viability, "uncertainty": 0.85, "model_version": MODEL_VERSION},
            "gates": gates,
            "duplicates": {"within_run": [], "within_library": [], "semantic": []},
            "status": "proposed", "rejection_reason": None,
            "shelf_life": {"type": "evergreen", "expires_at": None},
            "transcript_excerpt": text,
        })

    # rank, then reject failures and overlaps (rejections are kept: spec 1.4)
    cands.sort(key=lambda x: x["overall"]["viability"], reverse=True)
    kept: list[dict] = []
    for cd in cands:
        failed = [g for g in cd["gates"] if not g["passed"]]
        if failed:
            cd["status"], cd["rejection_reason"] = "rejected", "; ".join(f"{g['name']}: {g['reason']}" for g in failed)
            continue
        overl = next((k for k in kept if _overlap(cd, k) > 0.5), None)
        if overl:
            cd["status"] = "rejected"
            cd["rejection_reason"] = f"duplicate: >50% overlap with higher-ranked {overl['candidate_id']}"
            cd["duplicates"]["within_run"].append(overl["candidate_id"])
            cd["gates"].append({"name": "duplicate", "passed": False, "reason": cd["rejection_reason"]})
            continue
        if len(kept) >= c["max_candidates_per_source"]:
            cd["status"], cd["rejection_reason"] = "rejected", "below per-source cap"
            continue
        cd["gates"].append({"name": "duplicate", "passed": True, "reason": "no >50% overlap"})
        kept.append(cd)
    return {"source_id": source_id, "model_version": MODEL_VERSION,
            "counts": {"proposed": len(kept), "rejected": len(cands) - len(kept)},
            "candidates": cands}


def _music_gate(events: dict | None, start: int, end: int, a: dict) -> dict:
    """R26: suspected music blocks the candidate until mute/replace exists. Fails closed."""
    from ..analysis.audio_events import music_fraction
    if events is None or events.get("unscreened"):
        return {"name": "music_screen", "passed": False,
                "reason": "source not screened for music (model or runtime unavailable): fail closed"}
    frac = music_fraction(events, start, end, a["music_threshold"])
    return {"name": "music_screen", "passed": frac <= a["max_music_fraction"],
            "reason": f"music in {frac:.0%} of windows (max {a['max_music_fraction']:.0%}, threshold {a['music_threshold']})"
                      + ("" if frac <= a["max_music_fraction"] else "; mute/replace not implemented, so rejected")}


def _overlap(a: dict, b: dict) -> float:
    s = max(a["boundaries"]["start_us"], b["boundaries"]["start_us"])
    e = min(a["boundaries"]["end_us"], b["boundaries"]["end_us"])
    shorter = min(a["boundaries"]["end_us"] - a["boundaries"]["start_us"],
                  b["boundaries"]["end_us"] - b["boundaries"]["start_us"])
    return max(0, e - s) / max(shorter, 1)
