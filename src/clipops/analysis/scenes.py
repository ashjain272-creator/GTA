"""Stage 5 (spec 6.7), skeleton subset: scene-change timestamps via FFmpeg scdet."""
from __future__ import annotations

import re
from pathlib import Path

from ..media import run

_SC = re.compile(r"lavfi\.scd\.score:\s*([\d.]+),\s*lavfi\.scd\.time:\s*([\d.]+)")


def scene_cuts(path: Path, threshold: float, analysis_width: int = 320) -> list[dict]:
    p = run(["ffmpeg", "-hide_banner", "-nostats", "-v", "verbose", "-i", str(path), "-an",
             "-vf", f"scale={analysis_width}:-2,scdet=threshold={threshold}", "-f", "null", "-"],
            code="scene_detect_failed")
    return [{"time_us": int(float(t) * 1e6), "score": float(s)}
            for s, t in _SC.findall(p.stderr.decode(errors="replace"))]
