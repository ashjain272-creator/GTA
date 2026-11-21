"""Stage 1 (spec 6.2): probe and record the source's technical facts."""
from __future__ import annotations

from pathlib import Path

from ..media import ffprobe, frac
from ..runreport import StageFailed


def probe_source(path: Path) -> dict:
    info = ffprobe(path)
    v = [s for s in info["streams"] if s.get("codec_type") == "video"]
    a = [s for s in info["streams"] if s.get("codec_type") == "audio"]
    if not v:
        raise StageFailed("no_video_stream", "data", f"{path.name} has no video stream")
    vs = v[0]
    r_fps, avg_fps = frac(vs.get("r_frame_rate")), frac(vs.get("avg_frame_rate"))
    vfr = bool(r_fps and avg_fps and abs(r_fps - avg_fps) / r_fps > 0.01)
    duration = float(info["format"].get("duration") or vs.get("duration") or 0)
    if duration <= 0:
        raise StageFailed("no_duration", "data", "source duration unknown or zero")
    manifest = {
        "path": str(path),
        "container": info["format"].get("format_name"),
        "duration_us": int(round(duration * 1e6)),
        "bytes": int(info["format"].get("size") or 0),
        "video": {
            "codec": vs.get("codec_name"), "width": vs.get("width"), "height": vs.get("height"),
            "pix_fmt": vs.get("pix_fmt"), "r_frame_rate": vs.get("r_frame_rate"),
            "avg_frame_rate": vs.get("avg_frame_rate"), "variable_frame_rate_suspected": vfr,
            "color_transfer": vs.get("color_transfer"), "color_primaries": vs.get("color_primaries"),
            "hdr_suspected": vs.get("color_transfer") in ("smpte2084", "arib-std-b67"),
        },
        "audio_streams": [
            {"index": s["index"], "codec": s.get("codec_name"), "channels": s.get("channels"),
             "sample_rate": int(s.get("sample_rate") or 0),
             "language": (s.get("tags") or {}).get("language"),
             "title": (s.get("tags") or {}).get("title")}
            for s in a
        ],
    }
    return manifest


def probe_warnings(manifest: dict) -> list[tuple[str, str]]:
    w = []
    if manifest["video"]["variable_frame_rate_suspected"]:
        w.append(("vfr", "variable frame rate suspected; timing normalisation not yet implemented (spec 5.8)"))
    if manifest["video"]["hdr_suspected"]:
        w.append(("hdr", "HDR transfer detected; tone mapping not yet implemented"))
    if not manifest["audio_streams"]:
        w.append(("no_audio", "no audio stream: transcription and audio analysis will be skipped"))
    if len(manifest["audio_streams"]) > 1:
        w.append(("multi_audio", "multiple audio streams; first stream used (track-role classification pending)"))
    return w
