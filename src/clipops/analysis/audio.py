"""Stage 4 (spec 6.6), skeleton subset: momentary loudness curve and silences."""
from __future__ import annotations

import re
from pathlib import Path

from ..media import run

_M = re.compile(r"t:\s*([\d.]+)\s+TARGET:.*?M:\s*(-?[\d.]+|-inf|nan)")


def loudness_curve(path: Path) -> list[tuple[float, float]]:
    """(time_s, momentary LUFS) pairs from ebur128, roughly every 100 ms."""
    p = run(["ffmpeg", "-hide_banner", "-nostats", "-v", "verbose", "-i", str(path), "-vn",
             "-af", "ebur128=framelog=verbose", "-f", "null", "-"], code="loudness_failed")
    curve = []
    for t, m in _M.findall(p.stderr.decode(errors="replace")):
        val = -120.0 if m in ("-inf", "nan") else float(m)
        curve.append((float(t), max(val, -120.0)))
    return curve


def summarise(curve: list[tuple[float, float]]) -> dict:
    vals = [m for _, m in curve if m > -70]
    if not vals:
        return {"frames": len(curve), "speechless_or_silent": True}
    vals_sorted = sorted(vals)
    return {"frames": len(curve), "speechless_or_silent": False,
            "p50_lufs": round(vals_sorted[len(vals) // 2], 2),
            "p95_lufs": round(vals_sorted[int(len(vals) * 0.95) - 1], 2),
            "max_lufs": round(vals_sorted[-1], 2)}
