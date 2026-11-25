"""Acquire a video from a URL for a source that already has rights (AM-29, ADR-0013).

Operator instruction (2026-11-25): footage the operator owns (class A) or has
written creator permission for (class B) may be downloaded from YouTube with
a standard downloader (yt-dlp), even though YouTube offers no official
download API. This knowingly accepts YouTube Terms-of-Service risk (R36).

Still forbidden, and enforced here:
- any URL without a class A/B declaration (E/F refused before any network call);
- DRM-protected media (yt-dlp refuses it; we never add decryption);
- logins, cookies, or account credentials;
- proxies, IP rotation, or other rate-limit/bot-check evasion;
- downloading more than the single item named by the URL (no channel crawls).
"""
from __future__ import annotations

import datetime as _dt
from pathlib import Path

from ..runreport import StageFailed
from .classify import classify_url

SUPPORTED = {("youtube", "video"), ("youtube", "short")}


def ydl_options(out_dir: Path, cfg: dict) -> dict:
    a = cfg["acquire"]
    return {
        "outtmpl": str(out_dir / "%(id)s.%(ext)s"),
        "format": a["format"],
        "merge_output_format": "mp4",
        "noplaylist": True,                 # one item only
        "ratelimit": a["max_bytes_per_s"],   # be a polite client
        "sleep_interval_requests": a["sleep_between_requests_s"],
        "retries": 3,
        "quiet": True,
        "no_warnings": False,
        "writeinfojson": False,
        "allow_unplayable_formats": False,   # never DRM
        # deliberately absent: cookiefile, cookiesfrombrowser, username, password, proxy, source_address
    }


FORBIDDEN_KEYS = {"cookiefile", "cookiesfrombrowser", "username", "password", "proxy", "source_address",
                  "allow_unplayable_formats_true"}


def check_preconditions(url: str, klass: str, grant: dict | None) -> dict:
    c = classify_url(url)
    if klass in ("E", "F"):
        raise StageFailed("rights_refused", "policy", f"class {klass}: no download (spec 4.3)")
    if klass not in ("A", "B"):
        raise StageFailed("rights_refused", "policy", f"class {klass} cannot be acquired by URL; only A or B (AM-29)")
    if klass == "B" and not (grant and grant.get("document_ref")):
        raise StageFailed("grant_missing", "policy", "class B needs a grant file with document_ref (creator's written permission)")
    if (c["platform"], c["object"]) not in SUPPORTED:
        raise StageFailed("unsupported_url", "config",
                          f"{c['platform']}/{c['object']} not supported for acquisition (single YouTube videos only)")
    return c


def acquire(url: str, klass: str, grant: dict | None, cfg: dict, out_dir: Path) -> dict:
    c = check_preconditions(url, klass, grant)
    try:
        import yt_dlp
    except ImportError as e:
        raise StageFailed("downloader_missing", "config", "yt-dlp not installed: uv sync --extra acquire") from e
    opts = ydl_options(out_dir, cfg)
    assert not (FORBIDDEN_KEYS & set(opts)), "forbidden downloader option present"
    out_dir.mkdir(parents=True, exist_ok=True)
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            path = Path(ydl.prepare_filename(info)).with_suffix(".mp4")
    except Exception as e:  # noqa: BLE001 - recorded verbatim, no retry tricks
        msg = str(e)
        if "DRM" in msg:
            raise StageFailed("drm_protected", "policy", "media is DRM-protected; refused") from e
        raise StageFailed("download_failed", "transient", msg[:400]) from e
    if not path.is_file():
        raise StageFailed("download_failed", "data", f"expected file missing: {path.name}")
    return {"path": path, "provenance": {
        "url": url, "platform": c["platform"], "video_id": info.get("id"), "title": info.get("title"),
        "uploader": info.get("uploader"), "channel_id": info.get("channel_id"),
        "format_id": info.get("format_id"), "downloader": f"yt-dlp {yt_dlp.version.__version__}",
        "downloaded_at": _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds"),
        "basis": "operator instruction 2026-11-25 (AM-29); YouTube ToS risk accepted (R36)"}}
