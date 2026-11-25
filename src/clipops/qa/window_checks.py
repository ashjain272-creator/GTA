"""Checks on a source window before editing: flash risk and black edges (fades)."""
from __future__ import annotations

import re
import tempfile
from pathlib import Path

from ..media import run
from .visual import flash_check

_BLACK = re.compile(r"black_start:([\d.]+)\s+black_end:([\d.]+)")


def source_flash_risk(src: Path, start_s: float, dur_s: float, cfg: dict) -> dict:
    """Measure flashing in the source window; if unsafe, choose a photosensitivity setting that fixes it."""
    q = cfg["qa"]
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td) / "w.mp4"
        run(["ffmpeg", "-v", "error", "-y", "-ss", f"{start_s:.3f}", "-t", f"{dur_s:.3f}", "-i", str(src),
             "-an", "-vf", "scale=320:-2", "-c:v", "libx264", "-crf", "20", "-preset", "veryfast", str(tmp)],
            code="flash_probe_failed")
        r = flash_check(tmp, q["max_flashes_per_s"])
        if r["passed"]:
            return {"risk": False, "max_flashes_per_s": r["max_flashes_per_s"], "mitigation": None}
        for frames, thr in cfg["flash_mitigation"]["ladder"]:
            fixed = Path(td) / f"m_{frames}_{thr}.mp4"
            run(["ffmpeg", "-v", "error", "-y", "-i", str(tmp), "-vf", f"photosensitivity=f={frames}:t={thr}",
                 "-c:v", "libx264", "-crf", "20", "-preset", "veryfast", str(fixed)], code="flash_fix_failed")
            if flash_check(fixed, q["max_flashes_per_s"])["passed"]:
                return {"risk": True, "max_flashes_per_s": r["max_flashes_per_s"],
                        "mitigation": {"frames": frames, "threshold": thr}}
        return {"risk": True, "max_flashes_per_s": r["max_flashes_per_s"],
                "mitigation": {"frames": 30, "threshold": 0.2, "note": "strongest setting; QA decides"}}


def black_edges(src: Path, start_us: int, end_us: int, min_s: float = 0.15) -> dict:
    """Black stretches touching either end of the window (fade in/out) → trimmed boundaries."""
    a, dur = start_us / 1e6, (end_us - start_us) / 1e6
    p = run(["ffmpeg", "-hide_banner", "-nostats", "-ss", f"{a:.3f}", "-t", f"{dur:.3f}", "-i", str(src), "-an",
             "-vf", f"scale=320:-2,blackdetect=d={min_s}:pix_th=0.10", "-f", "null", "-"], code="black_probe_failed")
    out = {}
    for bs, be in _BLACK.findall(p.stderr.decode(errors="replace")):
        bs, be = float(bs), float(be)
        if bs <= 0.1:
            out["start_us"] = start_us + int(be * 1e6)
        if be >= dur - 0.1:
            out["end_us"] = start_us + int(bs * 1e6)
    return out
