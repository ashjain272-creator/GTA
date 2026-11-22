"""Pixel-level QA (spec 10.3 picture, 4.9 safety): photosensitive flashing and
measured caption placement.

Flash rule source: W3C WCAG 2.2 Understanding SC 2.3.1 (E-033). A *general flash*
is "a pair of opposing changes in relative luminance of 10% or more of the
maximum relative luminance (1.0) where the relative luminance of the darker
image is below 0.80"; content fails when there are more than three flashes in
any one-second period over a sufficiently large area.

Approximations, stated rather than hidden:
- Area: luminance is averaged over a coarse grid of blocks (each about 1/9 of
  the frame) plus the whole frame. On a phone held at normal distance, a 10°
  field covers most of the screen width, so a block of 1/9 of the frame
  exceeds the 25%-of-10° area limit. This errs towards flagging (conservative).
- The red-flash test is NOT implemented. This is reported as a limitation in
  every result.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

from ..media import ffprobe, frac, run

GRID = (3, 3)


def _decode_rgb(path: Path, width: int, height: int, fps: float | None = None) -> tuple[np.ndarray, float]:
    info = ffprobe(path)
    vs = next(s for s in info["streams"] if s["codec_type"] == "video")
    src_fps = frac(vs.get("avg_frame_rate")) or 30.0
    vf = f"scale={width}:{height}:flags=area"
    if fps:
        vf = f"fps={fps}," + vf
    raw = run(["ffmpeg", "-v", "error", "-i", str(path), "-vf", vf, "-pix_fmt", "rgb24",
               "-f", "rawvideo", "-"], code="decode_failed").stdout
    frames = np.frombuffer(raw, np.uint8).reshape(-1, height, width, 3)
    return frames, (fps or src_fps)


def relative_luminance(rgb: np.ndarray) -> np.ndarray:
    """sRGB → relative luminance per WCAG (linearise, then Rec.709 weights)."""
    c = rgb.astype(np.float32) / 255.0
    lin = np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    return lin[..., 0] * 0.2126 + lin[..., 1] * 0.7152 + lin[..., 2] * 0.0722


def transitions(series: np.ndarray, delta: float = 0.10, dark_max: float = 0.80) -> list[int]:
    """Frame indices where a qualifying luminance change completes.

    A change counts when luminance moves by >= delta from the last extreme in the
    opposite direction and the darker side is below dark_max (hysteresis
    tracking of extremes, so slow ramps count once, not per frame).
    """
    out: list[int] = []
    if len(series) < 2:
        return out
    lo = hi = float(series[0])          # extremes since the last counted transition
    direction = 0                       # +1 last counted was a rise, -1 a fall, 0 none yet
    for i in range(1, len(series)):
        v = float(series[i])
        lo, hi = min(lo, v), max(hi, v)
        if direction != 1 and v - lo >= delta and lo < dark_max:
            out.append(i)
            direction, lo, hi = 1, v, v
        elif direction != -1 and hi - v >= delta and v < dark_max:
            out.append(i)
            direction, lo, hi = -1, v, v
    return out


def max_flashes_per_second(trans: list[int], fps: float) -> float:
    """Largest number of flashes (pairs of opposing transitions) in any 1-s window."""
    if not trans:
        return 0.0
    w = max(1, int(round(fps)))
    best, j = 0, 0
    for i in range(len(trans)):
        while trans[i] - trans[j] >= w:
            j += 1
        best = max(best, i - j + 1)
    return best / 2.0


def flash_check(path: Path, max_flashes: float = 3.0, analysis_size: tuple[int, int] = (90, 160)) -> dict:
    w, h = analysis_size
    frames, fps = _decode_rgb(path, w, h)
    lum = relative_luminance(frames)                       # (n, h, w)
    series = {"full": lum.mean(axis=(1, 2))}
    gy, gx = GRID
    for by in range(gy):
        for bx in range(gx):
            blk = lum[:, by * h // gy:(by + 1) * h // gy, bx * w // gx:(bx + 1) * w // gx]
            series[f"block_{by}{bx}"] = blk.mean(axis=(1, 2))
    worst_name, worst, worst_t = "full", 0.0, None
    for name, s in series.items():
        tr = transitions(s)
        f = max_flashes_per_second(tr, fps)
        if f > worst:
            worst_name, worst, worst_t = name, f, (tr[0] / fps if tr else None)
    return {"max_flashes_per_s": worst, "region": worst_name, "first_transition_s": worst_t,
            "passed": worst <= max_flashes, "fps": fps, "frames": int(len(lum)),
            "limitations": ["red-flash threshold not implemented",
                            "area approximated by a 3x3 block grid (conservative)"]}


def caption_bounds(ass_path: Path, cues: list[dict], width: int, height: int) -> list[dict]:
    """Render captions alone on black and measure each cue's pixel bounding box."""
    out = []
    if not cues:
        return out
    dur = max(c["end_us"] for c in cues) / 1e6 + 0.5
    esc = str(ass_path).replace("\\", "/").replace(":", r"\:").replace("'", r"\'")
    for c in cues:
        t = (c["start_us"] + c["end_us"]) / 2e6
        raw = run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", f"color=c=black:s={width}x{height}:d={dur:.2f}:r=10",
                   "-vf", f"subtitles=filename='{esc}'", "-ss", f"{t:.3f}", "-frames:v", "1",
                   "-pix_fmt", "gray", "-f", "rawvideo", "-"], code="caption_render_failed").stdout
        img = np.frombuffer(raw, np.uint8).reshape(height, width)
        ys, xs = np.nonzero(img > 40)
        if len(xs) == 0:
            out.append({"text": c["text"], "t_s": round(t, 3), "bbox": None})
            continue
        out.append({"text": c["text"], "t_s": round(t, 3),
                    "bbox": [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())]})
    return out


def safe_area_violations(bounds: list[dict], width: int, height: int, sa: dict) -> list[dict]:
    left, right = sa["side_px"], width - sa["side_px"]
    top, bottom = sa["top_px"], height - sa["bottom_px"]
    bad = []
    for b in bounds:
        if b["bbox"] is None:
            bad.append({**b, "problem": "caption not rendered (no pixels found)"})
            continue
        x0, y0, x1, y1 = b["bbox"]
        problems = []
        if x0 < left or x1 > right:
            problems.append(f"horizontal extent {x0}-{x1} outside {left}-{right}")
        if y0 < top or y1 > bottom:
            problems.append(f"vertical extent {y0}-{y1} outside {top}-{bottom}")
        if problems:
            bad.append({**b, "problem": "; ".join(problems)})
    return bad
