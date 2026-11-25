"""Acquire a video from a URL for a source that already has rights (AM-29, ADR-0013).

Operator instruction (2026-11-25): footage the operator owns (class A) or has
written creator permission for (class B) may be downloaded from YouTube with
a standard downloader (yt-dlp), even though YouTube offers no official
download API. This knowingly accepts YouTube Terms-of-Service risk (R36).

Widened by operator instruction (2026-11-25, AM-30):
- class E (no permission) is accepted when the operator records an
  attestation (their stated basis, e.g. a fair-use claim). Monetisation is forced off;
- the operator's own exported cookie file may be used (path from an env var;
  never logged or stored in the repo);
- channels and playlists are allowed for class A and for class B grants whose
  scope covers them, capped at `acquire.max_items`.

Still forbidden, and enforced here (declined by the assistant):
- DRM-protected media (yt-dlp refuses it; we never add decryption);
- proxies, IP rotation, TLS/browser impersonation, or other rate-limit or
  bot-check evasion;
- class F, and channel or playlist crawling for class E.
"""
from __future__ import annotations

import datetime as _dt
import os
from pathlib import Path

from ..runreport import StageFailed
from .classify import classify_url

SINGLE = {("youtube", "video"), ("youtube", "short")}
MULTI = {("youtube", "channel"), ("youtube", "playlist")}


def ydl_options(out_dir: Path, cfg: dict, multi: bool = False) -> dict:
    a = cfg["acquire"]
    opts = {
        "outtmpl": str(out_dir / "%(id)s.%(ext)s"),
        "format": a["format"],
        "merge_output_format": "mp4",
        "noplaylist": not multi,
        "ratelimit": a["max_bytes_per_s"],   # be a polite client
        "sleep_interval_requests": a["sleep_between_requests_s"],
        "retries": 3,
        "quiet": True,
        "no_warnings": False,
        "writeinfojson": False,
        "allow_unplayable_formats": False,   # never DRM
        # deliberately absent: proxy, source_address, impersonate, cookiesfrombrowser, username, password
    }
    if multi:
        opts["playlistend"] = a["max_items"]
    cookie_path = os.environ.get(a["cookies_file_env"]) if a.get("cookies_file_env") else None
    if cookie_path:
        if not Path(cookie_path).is_file():
            raise StageFailed("cookies_missing", "config", f"${a['cookies_file_env']} points to a missing file")
        opts["cookiefile"] = cookie_path            # operator's own exported cookies (AM-30)
    return opts


FORBIDDEN_KEYS = {"proxy", "source_address", "impersonate", "cookiesfrombrowser", "username", "password",
                  "geo_bypass", "geo_bypass_country", "geo_bypass_ip_block"}


def check_preconditions(url: str, klass: str, grant: dict | None, attestation: str | None = None) -> dict:
    c = classify_url(url)
    key = (c["platform"], c["object"])
    if klass == "F":
        raise StageFailed("rights_refused", "policy", "class F (prohibited): refused (spec 4.3)")
    if klass == "E" and not (attestation and attestation.strip()):
        raise StageFailed("attestation_missing", "policy",
                          "class E needs --attest '<your basis>' (AM-30); nothing downloaded")
    if klass not in ("A", "B", "E"):
        raise StageFailed("rights_refused", "policy", f"class {klass} cannot be acquired by URL")
    if klass == "B" and not (grant and grant.get("document_ref")):
        raise StageFailed("grant_missing", "policy", "class B needs a grant file with document_ref (creator's written permission)")
    if key in MULTI:
        scope = ((grant or {}).get("scope") or {})
        covered = klass == "A" or (klass == "B" and (scope.get("all_videos") or url in scope.get("collections", [])))
        if not covered:
            raise StageFailed("crawl_refused", "policy",
                              "channels/playlists need class A, or a class B grant with scope.all_videos or this URL in scope.collections")
        c["multi"] = True
    elif key in SINGLE:
        c["multi"] = False
    else:
        raise StageFailed("unsupported_url", "config", f"{c['platform']}/{c['object']} not supported for acquisition")
    return c


def acquire(url: str, klass: str, grant: dict | None, cfg: dict, out_dir: Path,
            attestation: str | None = None) -> dict:
    c = check_preconditions(url, klass, grant, attestation)
    try:
        import yt_dlp
    except ImportError as e:
        raise StageFailed("downloader_missing", "config", "yt-dlp not installed: uv sync --extra acquire") from e
    opts = ydl_options(out_dir, cfg, multi=c["multi"])
    assert not (FORBIDDEN_KEYS & set(opts)), "forbidden downloader option present"
    out_dir.mkdir(parents=True, exist_ok=True)
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            entries = [e for e in (info.get("entries") or [info]) if e]
            paths = [Path(ydl.prepare_filename(e)).with_suffix(".mp4") for e in entries]
    except Exception as e:  # noqa: BLE001 - recorded verbatim; no evasion retries
        msg = str(e)
        if "DRM" in msg:
            raise StageFailed("drm_protected", "policy", "media is DRM-protected; refused") from e
        if "confirm you" in msg.lower() or "bot" in msg.lower():
            raise StageFailed("bot_check", "policy",
                              "YouTube asked for a bot check; stopping (evasion is not implemented)") from e
        raise StageFailed("download_failed", "transient", msg[:400]) from e
    items = []
    for e, p in zip(entries, paths):
        if not p.is_file():
            continue
        items.append({"path": p, "provenance": {
            "url": e.get("webpage_url") or url, "requested_url": url, "platform": c["platform"],
            "video_id": e.get("id"), "title": e.get("title"), "uploader": e.get("uploader"),
            "channel_id": e.get("channel_id"), "format_id": e.get("format_id"),
            "downloader": f"yt-dlp {yt_dlp.version.__version__}", "cookies_used": "cookiefile" in opts,
            "downloaded_at": _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds"),
            "basis": ("operator attestation: " + attestation if klass == "E" else f"class {klass}")
                     + "; YouTube ToS risk accepted (AM-29/30, R36)"}})
    if not items:
        raise StageFailed("download_failed", "data", "no files were produced")
    return {"items": items}
