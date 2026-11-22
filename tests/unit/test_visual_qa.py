"""Photosensitive flash detection and caption bound measurement (real FFmpeg renders)."""
from __future__ import annotations

import shutil
from pathlib import Path

import numpy as np
import pytest

from clipops import config
from clipops.media import run
from clipops.qa.visual import (caption_bounds, flash_check, max_flashes_per_second,
                               safe_area_violations, transitions)
from clipops.render.subtitles import build_ass

pytestmark = pytest.mark.media
CFG = config.load(Path(__file__).resolve().parents[2])


def test_transitions_count_opposing_changes_once():
    s = np.array([0.0, 0.0, 0.9, 0.9, 0.0, 0.0, 0.9])      # up, down, up
    assert transitions(s) == [2, 4, 6]
    ramp = np.linspace(0, 0.9, 30)                         # slow ramp counts once
    assert len(transitions(ramp)) == 1
    small = np.array([0.5, 0.55, 0.5, 0.55])               # below 10% delta
    assert transitions(small) == []
    bright = np.array([0.85, 0.99, 0.85, 0.99])            # darker side >= 0.80: not a flash
    assert transitions(bright) == []


def test_flashes_per_second_window():
    # 8 transitions within 30 frames at 30 fps → 4 flashes in one second
    assert max_flashes_per_second([0, 4, 8, 12, 16, 20, 24, 28], 30) == 4.0
    assert max_flashes_per_second([0, 40, 80], 30) == 0.5


def _flicker(tmp_path, hz):
    p = tmp_path / f"flicker_{hz}.mp4"
    run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",
         "color=c=black:s=180x320:r=30:d=3", "-vf",
         f"geq=lum='if(lt(mod(T*{hz},1),0.5),235,16)':cb=128:cr=128,format=yuv420p",
         "-c:v", "libx264", "-qp", "0", str(p)])
    return p


def test_fast_flicker_fails(tmp_path):
    r = flash_check(_flicker(tmp_path, 10))
    assert not r["passed"] and r["max_flashes_per_s"] >= 8


def test_slow_alternation_passes(tmp_path):
    r = flash_check(_flicker(tmp_path, 1))
    assert r["passed"], r


def test_caption_bounds_measure_rendered_pixels(tmp_path):
    s = dict(CFG["render"]["subtitles"])
    cues = [{"start_us": 0, "end_us": 1_000_000, "text": "Hello there", "min_confidence": 1.0}]
    ass = tmp_path / "a.ass"
    ass.write_text(build_ass(cues, 1080, 1920, s))
    b = caption_bounds(ass, cues, 1080, 1920)[0]["bbox"]
    assert b is not None
    x0, y0, x1, y1 = b
    assert 1920 - s["margin_v"] - 120 < y1 <= 1920 - s["margin_v"] + 10     # bottom-aligned at margin
    assert abs((x0 + x1) / 2 - 540) < 20                                    # centred
    sa = CFG["qa"]["safe_area"]
    assert safe_area_violations([{"text": "x", "t_s": 0.5, "bbox": b}], 1080, 1920, sa) == []


def test_oversized_caption_is_flagged(tmp_path):
    s = dict(CFG["render"]["subtitles"], font_size=160, margin_h=10)
    cues = [{"start_us": 0, "end_us": 1_000_000, "text": "AN EXTREMELY LONG CAPTION LINE THAT OVERFLOWS",
             "min_confidence": 1.0}]
    ass = tmp_path / "b.ass"
    ass.write_text(build_ass(cues, 1080, 1920, s))
    bounds = caption_bounds(ass, cues, 1080, 1920)
    assert safe_area_violations(bounds, 1080, 1920, CFG["qa"]["safe_area"])
