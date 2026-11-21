"""Stage: render a plan to a 9:16 short (spec 9.2), skeleton grade.

Two-pass audio loudness normalisation (measure, then apply) so the output hits
the configured target instead of guessing.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from ..media import run
from ..runreport import StageFailed
from .subtitles import build_ass

_JSON = re.compile(r"\{[^{}]*\"input_i\"[^{}]*\}", re.S)


def _filter_path(p: Path) -> str:
    # escape for the FFmpeg filtergraph parser
    return str(p).replace("\\", "/").replace(":", r"\:").replace("'", r"\'")


def measure_loudness(src: Path, start_s: float, dur_s: float, target: float, tp: float) -> dict:
    p = run(["ffmpeg", "-hide_banner", "-nostats", "-ss", f"{start_s:.3f}", "-t", f"{dur_s:.3f}",
             "-i", str(src), "-vn", "-af", f"loudnorm=I={target}:TP={tp}:LRA=11:print_format=json",
             "-f", "null", "-"], code="loudness_measure_failed")
    m = _JSON.search(p.stderr.decode(errors="replace"))
    if not m:
        raise StageFailed("loudness_parse_failed", "bug", "loudnorm JSON not found in output")
    return json.loads(m.group(0))


def render(plan: dict, src: Path, out_dir: Path, cfg: dict) -> dict:
    r = cfg["render"]
    seg = plan["timeline"][0]
    start_s, dur_s = seg["src_start_us"] / 1e6, (seg["src_end_us"] - seg["src_start_us"]) / 1e6
    short_id = "short_" + plan["plan_id"][5:]
    out_dir.mkdir(parents=True, exist_ok=True)
    ass_path = out_dir / f"{short_id}.ass"
    ass_path.write_text(build_ass(plan["subtitles"]["cues"], r["width"], r["height"], r["subtitles"]))
    out = out_dir / f"{short_id}.mp4"

    meas = measure_loudness(src, start_s, dur_s, r["loudness_target_lufs"], r["true_peak_dbtp"])
    af = (f"loudnorm=I={r['loudness_target_lufs']}:TP={r['true_peak_dbtp']}:LRA=11:"
          f"measured_I={meas['input_i']}:measured_TP={meas['input_tp']}:measured_LRA={meas['input_lra']}:"
          f"measured_thresh={meas['input_thresh']}:offset={meas['target_offset']}:linear=true,"
          f"aresample=48000,"
          # sample-peak limiter below the true-peak ceiling: loudnorm's linear mode does not
          # guarantee the ceiling (measured -1.06 dBTP vs -1.5 target on 2026-11-21)
          f"alimiter=limit={10 ** ((r['true_peak_dbtp'] - 0.5) / 20):.4f}:attack=5:release=50:level=disabled")
    W, H = r["width"], r["height"]
    tail = (f"[bg][fg]overlay=(W-w)/2:(H-h)/2:shortest=1,fps={r['fps']},"
            f"subtitles=filename='{_filter_path(ass_path)}',format=yuv420p,setsar=1[v]")
    if r["background"] == "blur":
        vf = (f"[0:v]split[s1][s2];"
              f"[s1]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},"
              f"boxblur=24:2,eq=brightness=-0.12[bg];"
              f"[s2]scale={W}:-2[fg];" + tail)
    elif r["background"] == "black":
        vf = f"color=c=black:s={W}x{H}:d={dur_s:.3f}[bg];[0:v]scale={W}:-2[fg];" + tail
    else:
        raise StageFailed("bad_config", "config", f"render.background={r['background']!r}")
    run(["ffmpeg", "-hide_banner", "-v", "error", "-y", "-ss", f"{start_s:.3f}", "-t", f"{dur_s:.3f}",
         "-i", str(src), "-filter_complex", vf, "-map", "[v]", "-map", "0:a:0?", "-af", af,
         "-c:v", r["video_codec"], "-crf", str(r["crf"]), "-preset", r["preset"],
         "-c:a", r["audio_codec"], "-b:a", r["audio_bitrate"], "-movflags", "+faststart", str(out)],
        code="render_failed")
    return {"short_id": short_id, "plan_id": plan["plan_id"], "path": str(out), "ass_path": str(ass_path),
            "expected_duration_us": plan["duration_us"], "loudness_first_pass": meas,
            "encoder": r["video_codec"]}
