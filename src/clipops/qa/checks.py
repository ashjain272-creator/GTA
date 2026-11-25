"""Objective output checks (spec 10.3), skeleton subset.

Each check returns pass/fail with the measured value. Nothing here infers
quality from an exit code (Principle 5): every value is measured on the file.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from ..media import ffprobe, run
from ..runreport import StageFailed
from ..render.vertical import _JSON
from .visual import caption_bounds, flash_check, safe_area_violations

_BLACK = re.compile(r"black_start:([\d.]+)\s+black_end:([\d.]+)\s+black_duration:([\d.]+)")
_SIL_START = re.compile(r"silence_start:\s*(-?[\d.]+)")
_SIL_END = re.compile(r"silence_end:\s*([\d.]+)\s*\|\s*silence_duration:\s*([\d.]+)")


def _check(name: str, passed: bool, measured, expected, note: str = "", severity: str = "blocking") -> dict:
    """severity: 'blocking' fails QA; 'review' passes QA but escalates to human review (spec 2.15)."""
    return {"name": name, "passed": bool(passed), "measured": measured, "expected": expected, "note": note,
            "severity": severity}


def run_qa(render_info: dict, plan: dict, cfg: dict, contact_dir: Path) -> dict:
    q, r = cfg["qa"], cfg["render"]
    path = Path(render_info["path"])
    checks: list[dict] = []

    # 1. container and streams
    info = ffprobe(path)
    v = [s for s in info["streams"] if s["codec_type"] == "video"]
    a = [s for s in info["streams"] if s["codec_type"] == "audio"]
    dur = float(info["format"]["duration"])
    exp_dur = render_info["expected_duration_us"] / 1e6
    checks.append(_check("streams", len(v) == 1 and len(a) == 1, {"video": len(v), "audio": len(a)},
                         {"video": 1, "audio": 1}))
    checks.append(_check("resolution", bool(v) and (v[0]["width"], v[0]["height"]) == (r["width"], r["height"]),
                         f"{v[0]['width']}x{v[0]['height']}" if v else None, f"{r['width']}x{r['height']}"))
    checks.append(_check("duration", abs(dur - exp_dur) <= q["duration_tolerance_s"], round(dur, 3),
                         f"{exp_dur:.3f} ± {q['duration_tolerance_s']}"))

    # 2. full decode, no errors
    p = run(["ffmpeg", "-hide_banner", "-v", "error", "-i", str(path), "-f", "null", "-"], code="decode_failed")
    errs = p.stderr.decode(errors="replace").strip()
    checks.append(_check("clean_decode", errs == "", errs[:300] or "no errors", "no decoder errors"))

    # 3. loudness (integrated and true peak) measured on the output
    p = run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(path), "-vn",
             "-af", f"loudnorm=I={r['loudness_target_lufs']}:TP={r['true_peak_dbtp']}:print_format=json",
             "-f", "null", "-"], code="loudness_failed")
    m = json.loads(_JSON.search(p.stderr.decode(errors="replace")).group(0))
    li, tp = float(m["input_i"]), float(m["input_tp"])
    checks.append(_check("integrated_loudness", abs(li - r["loudness_target_lufs"]) <= q["loudness_tolerance_lu"],
                         li, f"{r['loudness_target_lufs']} ± {q['loudness_tolerance_lu']} LUFS"))
    checks.append(_check("true_peak", tp <= r["true_peak_dbtp"], tp, f"<= {r['true_peak_dbtp']} dBTP"))

    # 4. black frames and silence
    p = run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(path),
             "-vf", "blackdetect=d=0.1:pix_th=0.10", "-af", f"silencedetect=n={q['silence_threshold_db']}dB:d=0.3",
             "-f", "null", "-"], code="detect_failed")
    err = p.stderr.decode(errors="replace")
    black_total = sum(float(d) for _, _, d in _BLACK.findall(err))
    sil = [float(d) for _, d in _SIL_END.findall(err)]
    starts = _SIL_START.findall(err)
    if len(starts) > len(sil):          # silence running to the end of file
        sil.append(dur - float(starts[-1]))
    longest_sil = max(sil, default=0.0)
    checks.append(_check("black_frames", black_total <= q["max_black_s"], round(black_total, 3), f"<= {q['max_black_s']} s"))
    checks.append(_check("longest_silence", longest_sil <= q["max_silence_s"], round(longest_sil, 3),
                         f"<= {q['max_silence_s']} s"))

    # 5. subtitles: timing inside the clip, reading speed, confidence, safe area by configuration
    cues = plan["subtitles"]["cues"]
    out_of_range = [c for c in cues if c["end_us"] / 1e6 > dur + 0.05 or c["start_us"] < 0]
    cps = [len(c["text"]) / max((c["end_us"] - c["start_us"]) / 1e6, 0.05) for c in cues]
    low_conf = [c["text"] for c in cues if c["min_confidence"] < 0.5]
    checks.append(_check("subtitle_timing", bool(cues) and not out_of_range, f"{len(cues)} cues, {len(out_of_range)} out of range",
                         ">=1 cue, all inside clip"))
    checks.append(_check("subtitle_reading_speed", max(cps, default=0) <= 25.0, round(max(cps, default=0), 1),
                         "<= 25 chars/s (HYPOTHESIS, spec 8.10)"))
    checks.append(_check("subtitle_confidence", not low_conf, low_conf or "all cues >= 0.5",
                         "no cue with a word below 0.5 confidence", "low-confidence cues need review", severity="review"))
    s = r["subtitles"]
    # measured, not configured: render captions alone and find their pixel bounds
    sa = q["safe_area"]
    hook = plan.get("hook") or {}
    bound_items = cues + ([{"start_us": hook["start_us"], "end_us": hook["end_us"], "text": hook["text"]}]
                          if hook.get("text") else [])
    bounds = caption_bounds(Path(render_info["ass_path"]), bound_items, r["width"], r["height"])
    bad = safe_area_violations(bounds, r["width"], r["height"], sa)
    heights = [b["bbox"][3] - b["bbox"][1] for b in bounds if b["bbox"]]
    checks.append(_check("subtitle_safe_area", not bad,
                         {"cues_measured": len(bounds), "violations": bad[:5]},
                         f"all caption pixels inside side {sa['side_px']}px, top {sa['top_px']}px, "
                         f"bottom {sa['bottom_px']}px (HYPOTHESIS, VERIFY per platform 8.9)"))
    checks.append(_check("subtitle_legible_size", bool(heights) and min(heights) >= q["min_caption_px"],
                         min(heights, default=0), f">= {q['min_caption_px']} px glyph height (HYPOTHESIS)"))

    # 5b. photosensitive flashing (WCAG 2.3.1 general-flash rule; red flash not implemented)
    fl = flash_check(path, q["max_flashes_per_s"])
    checks.append(_check("photosensitive_flash", fl["passed"], {k: fl[k] for k in ("max_flashes_per_s", "region", "first_transition_s")},
                         f"<= {q['max_flashes_per_s']} general flashes in any 1 s", "; ".join(fl["limitations"])))

    # 5c. music in the output (R26): the pipeline adds no music, so any detected music came from the source
    try:
        from ..analysis.audio_events import music_fraction, tag
        # screen the source-audio stem: registered SFX added by the edit are licensed and excluded
        ev = tag(Path(render_info.get("stem_path") or path), cfg)
        mf = music_fraction(ev, 0, int(dur * 1e6), cfg["analysis"]["music_threshold"])
        checks.append(_check("music_screen", mf <= cfg["analysis"]["max_music_fraction"], round(mf, 3),
                             f"<= {cfg['analysis']['max_music_fraction']} share of windows with music"))
    except StageFailed as e:
        checks.append(_check("music_screen", False, f"unscreened: {e.code}", "screen must run (fail closed)"))

    # 6. proxy inspection material: contact sheet (spec 2.15)
    contact_dir.mkdir(parents=True, exist_ok=True)
    sheet = contact_dir / f"{render_info['short_id']}_contact.png"
    step = q["contact_sheet_interval_s"]
    n = max(1, int(dur // step))
    cols = min(n, 6)
    rows = (n + cols - 1) // cols
    run(["ffmpeg", "-hide_banner", "-v", "error", "-y", "-i", str(path), "-vf",
         f"fps=1/{step},scale=216:384,tile={cols}x{rows}", "-frames:v", "1", "-update", "1", str(sheet)],
        code="contact_sheet_failed")

    passed = all(c["passed"] for c in checks if c["severity"] == "blocking")
    from ..storage.artefacts import sha256_file
    return {"short_id": render_info["short_id"], "path": str(path), "render_sha256": sha256_file(path),
            "passed": passed,
            "failed": [c["name"] for c in checks if not c["passed"] and c["severity"] == "blocking"],
            "review_flags": [c["name"] for c in checks if not c["passed"] and c["severity"] == "review"],
            "checks": checks,
            "contact_sheet": str(sheet),
            "creative_review": "not performed: reviewer ensemble not built (Phase 6); proxies saved for review",
            "publishable": False,
            "publishable_reason": "skeleton output: no creative review, no contribution (spec 4.7), autonomy L0"}
