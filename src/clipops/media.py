"""Thin, checked wrappers around ffmpeg/ffprobe. Every failure raises with stderr."""
from __future__ import annotations

import json
import subprocess
from fractions import Fraction
from pathlib import Path

import numpy as np

from .runreport import StageFailed


def run(cmd: list[str], *, timeout: float = 3600, code: str = "ffmpeg_failed") -> subprocess.CompletedProcess:
    try:
        p = subprocess.run(cmd, capture_output=True, timeout=timeout)
    except FileNotFoundError as e:
        raise StageFailed("tool_missing", "config", f"{cmd[0]} not found on PATH") from e
    except subprocess.TimeoutExpired as e:
        raise StageFailed("timeout", "transient", f"{cmd[0]} exceeded {timeout}s") from e
    if p.returncode != 0:
        tail = p.stderr.decode(errors="replace").strip().splitlines()[-5:]
        raise StageFailed(code, "data", f"{cmd[0]} exit {p.returncode}: {' | '.join(tail)}")
    return p


def ffprobe(path: Path) -> dict:
    p = run(["ffprobe", "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(path)],
            code="probe_failed")
    return json.loads(p.stdout)


def frac(s: str | None) -> float | None:
    if not s or s in ("0/0", "N/A"):
        return None
    return float(Fraction(s))


def decode_audio_f32(path: Path, start_s: float = 0.0, dur_s: float | None = None, sr: int = 16000) -> np.ndarray:
    cmd = ["ffmpeg", "-v", "error", "-ss", f"{start_s:.3f}"]
    if dur_s is not None:
        cmd += ["-t", f"{dur_s:.3f}"]
    cmd += ["-i", str(path), "-vn", "-ac", "1", "-ar", str(sr), "-f", "f32le", "-"]
    return np.frombuffer(run(cmd, code="audio_decode_failed").stdout, np.float32)
