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
VIDEO_EXT = (".mp4", ".mov", ".mkv", ".webm", ".ogv", ".m4v", ".avi")
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


def is_direct_file(url: str) -> bool:
    from urllib.parse import urlparse
    return urlparse(url).path.lower().endswith(VIDEO_EXT) and classify_url(url)["platform"] not in ("youtube", "twitch")


def acquire_direct(url: str, klass: str, grant: dict | None, cfg: dict, out_dir: Path) -> dict:
    """Plain HTTPS download of a video file the operator has rights to (owned, permitted or licensed).

    For Drive/Dropbox share links and openly licensed archives (e.g. Wikimedia Commons). Class C
    needs a licence grant (document_ref = licence URL, attribution). No auth, no evasion.
    """
    import hashlib
    import urllib.request
    from urllib.parse import unquote, urlparse
    if klass not in ("A", "B", "C"):
        raise StageFailed("rights_refused", "policy", f"direct downloads need class A, B or C (got {klass})")
    if klass in ("B", "C") and not (grant and grant.get("document_ref")):
        raise StageFailed("grant_missing", "policy", f"class {klass} needs a grant/licence file with document_ref")
    out_dir.mkdir(parents=True, exist_ok=True)
    name = unquote(Path(urlparse(url).path).name).replace(" ", "_")
    dest = out_dir / name
    a = cfg["acquire"]
    req = urllib.request.Request(url, headers={"User-Agent": a["user_agent"]})
    h = hashlib.sha256()
    total = 0
    try:
        with urllib.request.urlopen(req, timeout=60) as r, open(dest.with_suffix(dest.suffix + ".part"), "wb") as f:
            ctype = r.headers.get("Content-Type", "")
            if not (ctype.startswith(("video/", "application/octet-stream", "application/ogg"))):
                raise StageFailed("not_video", "data", f"server returned {ctype!r}, not a video file")
            while chunk := r.read(1 << 20):
                total += len(chunk)
                if total > a["max_bytes"]:
                    raise StageFailed("too_large", "config", f"file exceeds acquire.max_bytes ({a['max_bytes']})")
                h.update(chunk)
                f.write(chunk)
    except StageFailed:
        dest.with_suffix(dest.suffix + ".part").unlink(missing_ok=True)
        raise
    except Exception as e:  # noqa: BLE001
        dest.with_suffix(dest.suffix + ".part").unlink(missing_ok=True)
        raise StageFailed("download_failed", "transient", str(e)[:300]) from e
    dest.with_suffix(dest.suffix + ".part").replace(dest)
    return {"items": [{"path": dest, "provenance": {
        "url": url, "requested_url": url, "platform": "other", "video_id": None, "title": name,
        "bytes": total, "sha256": h.hexdigest(), "downloader": "urllib (direct file)",
        "downloaded_at": _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds"),
        "basis": f"class {klass}" + (f"; licence {grant.get('document_ref')}" if grant else "")}}]}


def acquire(url: str, klass: str, grant: dict | None, cfg: dict, out_dir: Path,
            attestation: str | None = None) -> dict:
    if is_direct_file(url):
        return acquire_direct(url, klass, grant, cfg, out_dir)
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
