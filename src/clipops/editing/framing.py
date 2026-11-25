"""Smart vertical framing (spec 8.9): follow the action instead of shrinking the frame.

Method (no ML model, runs anywhere): decode the segment small (192x108 at 10 fps),
take frame-to-frame motion energy, and for each frame find the 9:16 window
column range holding the most motion. The window centre is smoothed with a
dead zone, exponential smoothing and a speed limit, so the camera moves like
an operator, not a jittery tracker.

Layout decision, recorded with numbers:
- `tracked_crop` when motion is concentrated (most motion fits in the window);
- `blur_fill` (whole frame visible, blurred background) when action is spread
  across the frame or there is too little motion to track; never lose the subject.

Known limits (stated, not hidden): motion is a proxy for "the subject". A
static subject with a moving background (driving with a camera pan) defeats
it, and that case falls back to blur_fill through the concentration test.
Facecam detection is not implemented.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

from ..media import run

AW, AH, AFPS = 192, 108, 10


def _decode_gray(src: Path, start_s: float, dur_s: float) -> np.ndarray:
    raw = run(["ffmpeg", "-v", "error", "-ss", f"{start_s:.3f}", "-t", f"{dur_s:.3f}", "-i", str(src),
               "-vf", f"fps={AFPS},scale={AW}:{AH}:flags=area,format=gray", "-f", "rawvideo", "-"],
              code="framing_decode_failed").stdout
    return np.frombuffer(raw, np.uint8).reshape(-1, AH, AW).astype(np.float32)


def window_fraction(src_w: int, src_h: int) -> float:
    """Width of a full-height 9:16 window as a fraction of the source width."""
    return min(1.0, (src_h * 9 / 16) / src_w)


def _window_best(cols: np.ndarray, win: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    csum = np.cumsum(np.pad(cols, ((0, 0), (1, 0))), axis=1)
    mass = csum[:, win:] - csum[:, :-win]
    total = cols.sum(axis=1)
    frac = np.where(total > 0, mass.max(axis=1) / np.maximum(total, 1e-6), 0.0)
    return mass.argmax(axis=1), frac, total


def track(src: Path, start_s: float, dur_s: float, src_w: int, src_h: int, cfg: dict,
          camera: str | None = None, cut_times_s: list[float] | None = None) -> dict:
    f = cfg["framing"]
    frames = _decode_gray(src, start_s, dur_s)
    wf = window_fraction(src_w, src_h)
    if wf >= 0.99 or len(frames) < 3:
        return {"layout": "full", "reason": "source already vertical or too short", "keyframes": [],
                "window_fraction": wf, "subject_y": 0.5}
    win = max(1, int(round(wf * AW)))
    diffs = np.abs(np.diff(frames, axis=0))
    cut = diffs.mean(axis=(1, 2)) > f["cut_mean_diff"]             # scene cuts: reframe instantly
    for t in cut_times_s or []:                                     # plus cuts found by the scene-detection stage
        k = int(round((t - start_s) * AFPS)) - 1
        if 0 <= k < len(cut):
            cut[k] = True
    diffs[diffs < f["noise_floor"]] = 0.0
    diffs[cut] = 0.0
    m_best, m_frac, m_total = _window_best(diffs.sum(axis=1), win)
    active = (m_total > f["min_motion"] * AW) & ~cut
    # static saliency: contrast against the frame's median, for parked or slow subjects
    con = np.abs(frames[1:] - np.median(frames[1:], axis=(1, 2), keepdims=True))
    con[con < f["contrast_floor"]] = 0.0
    c_best, c_frac, c_total = _window_best(con.sum(axis=1), win)
    # subject vertical position: rows weighted by motion (or contrast when idle)
    rows_m, rows_c = diffs.sum(axis=2), con.sum(axis=2)
    yy = np.arange(AH)[None, :]
    ys = []
    for i in range(len(diffs)):
        r = rows_m[i] if active[i] else rows_c[i]
        ys.append(float((r * yy).sum() / r.sum() / AH) if r.sum() > 0 else 0.5)
    third_person = camera == "third_person"
    cx, path, reacq = 0.5, [], 0
    max_step = f["max_speed_frac_per_s"] / AFPS
    half = wf / 2
    for i in range(len(diffs)):
        if active[i] and m_frac[i] >= f["min_concentration"] * 0.8:
            target = (m_best[i] + win / 2) / AW
        elif c_total[i] > 0 and c_frac[i] >= f["min_concentration"]:
            target = (c_best[i] + win / 2) / AW
        else:
            target = 0.5 if third_person else cx
        if third_person:
            target = 0.5 + (target - 0.5) * f["third_person_follow"]  # GTA-style chase camera: player near centre
        if cut[i - 1] if i > 0 else False:
            cx = float(np.clip(target, half, 1 - half))               # a cut is already a jump: reframe at once
            reacq += 1
        elif abs(target - cx) > f["dead_zone_frac"]:
            cx += float(np.clip(f["smoothing"] * (target - cx), -max_step, max_step))
        cx = float(np.clip(cx, half, 1 - half))
        path.append(cx)
    path = [path[0]] + path
    conc = float(np.median(m_frac[active])) if active.any() else 0.0
    con_ok = float(np.mean(c_frac >= f["min_concentration"]))
    active_share = float(active.mean())
    if conc >= f["min_concentration"] and active_share >= f["min_active_share"]:
        layout, reason = "tracked_crop", f"motion concentrated: median {conc:.0%} fits a 9:16 window"
    elif con_ok >= 0.6:
        layout, reason = "tracked_crop", f"subject located by contrast in {con_ok:.0%} of frames"
    elif third_person:
        layout, reason = "tracked_crop", ("third-person game: camera keeps the player near the centre, so a "
                                          "centre-weighted crop is used despite spread motion")
    else:
        layout, reason = "blur_fill", f"no trackable subject (motion fit {conc:.0%}, contrast fit {con_ok:.0%})"
    keyframes = [{"t": round(i / AFPS, 2), "cx": round(c, 4)} for i, c in enumerate(path)]
    return {"layout": layout, "reason": reason, "concentration": round(conc, 3), "contrast_fit": round(con_ok, 3),
            "active_share": round(active_share, 3), "window_fraction": round(wf, 4), "scene_cuts_reframed": reacq,
            "subject_y": round(float(np.median(ys)), 3), "subject_y_track": [round(y, 3) for y in ys[::5]],
            "camera": camera or "unknown", "keyframes": keyframes}


def sendcmd_crop_x(keyframes: list[dict], src_w: int, crop_w: int, target: str = "crop@trk") -> str:
    """sendcmd script setting the crop's x (source pixels) at each keyframe time (source-relative)."""
    lines = []
    for k in keyframes:
        x = int(round(k["cx"] * src_w - crop_w / 2))
        x = max(0, min(src_w - crop_w, x))
        lines.append(f"{k['t']:.2f} {target} x {x};")
    return "\n".join(lines) + "\n"
