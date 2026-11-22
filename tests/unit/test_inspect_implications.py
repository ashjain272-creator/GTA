"""The hardware report's conclusions must match the machine (bugs seen on the operator's Mac, 2026-11-22)."""
from __future__ import annotations

import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "inspect_hardware", Path(__file__).resolve().parents[2] / "scripts" / "inspect_hardware.py")
ih = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ih)


def hw(system="Darwin", machine="arm64", ffmpeg=None, python="Python 3.9.6", free=6.7):
    return {"os": {"system": system, "machine": machine}, "gpu": {"devices": []},
            "memory": {"total_bytes": 16 << 30}, "cpu": {"logical_cores": 10},
            "ffmpeg": ffmpeg or {"present": False}, "software": {"python": python},
            "storage": {"volumes": [{"path": "/", "free_bytes": int(free * (1 << 30)), "total_bytes": 256 << 30}]}}


def test_apple_silicon_is_not_reported_as_cpu_only():
    text = "\n".join(ih.implications(hw()))
    assert "No CUDA GPU" not in text and "Apple Silicon" in text


def test_missing_ffmpeg_is_not_reported_as_no_hardware_encoder():
    text = "\n".join(ih.implications(hw()))
    assert "FFmpeg NOT INSTALLED" in text and "No working hardware encoder" not in text


def test_old_python_and_low_disk_are_flagged():
    text = "\n".join(ih.implications(hw()))
    assert "older than the project's minimum" in text
    assert "Low free disk space (6.7 GiB" in text


def test_linux_container_report_unchanged_in_substance():
    ff = {"present": True, "encode_tests": [{"encoder": "libx264", "ok": True}]}
    text = "\n".join(ih.implications(hw(system="Linux", machine="x86_64", ffmpeg=ff, python="Python 3.13.18", free=60)))
    assert "No CUDA GPU" in text and "No working hardware encoder" in text
    assert "older than" not in text and "Low free disk" not in text
