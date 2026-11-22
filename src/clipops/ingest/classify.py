"""URL classification without acquisition (spec 4.4, 4.15 test 1).

Identifies platform and object type from the URL text alone. Makes no network
request and never downloads. A URL with no declared rights is class E: the
only outputs are a classification record and a permission-request draft for
the operator to send (the system never contacts creators itself, spec 4.5).
"""
from __future__ import annotations

import re
from urllib.parse import parse_qs, urlparse

PATTERNS = [
    ("youtube", "video", r"(?:^|\.)youtube\.com$", r"^/watch$", lambda u: parse_qs(u.query).get("v", [None])[0]),
    ("youtube", "short", r"(?:^|\.)youtube\.com$", r"^/shorts/([\w-]+)", None),
    ("youtube", "channel", r"(?:^|\.)youtube\.com$", r"^/(?:@[\w.-]+|channel/[\w-]+|c/[\w-]+)", None),
    ("youtube", "playlist", r"(?:^|\.)youtube\.com$", r"^/playlist$", lambda u: parse_qs(u.query).get("list", [None])[0]),
    ("youtube", "video", r"^youtu\.be$", r"^/([\w-]+)", None),
    ("twitch", "clip", r"^clips\.twitch\.tv$", r"^/([\w-]+)", None),
    ("twitch", "clip", r"(?:^|\.)twitch\.tv$", r"^/[\w]+/clip/([\w-]+)", None),
    ("twitch", "vod", r"(?:^|\.)twitch\.tv$", r"^/videos/(\d+)", None),
    ("twitch", "channel", r"(?:^|\.)twitch\.tv$", r"^/([\w]+)/?$", None),
    ("tiktok", "video", r"(?:^|\.)tiktok\.com$", r"^/@[\w.-]+/video/(\d+)", None),
    ("instagram", "reel", r"(?:^|\.)instagram\.com$", r"^/reels?/([\w-]+)", None),
]


def classify_url(url: str) -> dict:
    u = urlparse(url.strip())
    if u.scheme not in ("http", "https") or not u.netloc:
        return {"url": url, "platform": "unknown", "object": "unknown", "object_id": None,
                "valid": False, "reason": "not an http(s) URL"}
    host = u.netloc.lower().split(":")[0]
    for platform, obj, host_re, path_re, qfn in PATTERNS:
        if re.search(host_re, host):
            m = re.match(path_re, u.path)
            if m:
                oid = qfn(u) if qfn else (m.group(1) if m.groups() else m.group(0).strip("/"))
                return {"url": url, "platform": platform, "object": obj, "object_id": oid, "valid": True}
    return {"url": url, "platform": "other", "object": "unknown", "object_id": None, "valid": True}


def class_e_outcome(url: str) -> dict:
    c = classify_url(url)
    return {
        "classification": c,
        "rights_class": "E",
        "acquired": False,
        "network_requests_made": 0,
        "limitation": ("No rights declared for this URL. Class E sources are limited to "
                       "metadata-level research; the system does not download them (spec 4.3). "
                       "Paths forward: the creator grants written permission (class B), a licence "
                       "(class C), or the creator's own sanctioned platform features (class D)."),
        "operator_actions": ["If you own this content, re-run with --declare-rights A and provide the original file.",
                             "Otherwise, send the drafted permission request (edit before sending)."],
        "permission_request_draft": permission_request(c),
    }


def permission_request(c: dict) -> str:
    what = {"channel": "your channel's videos", "video": "your video", "short": "your Short",
            "clip": "your clip", "vod": "your stream VOD", "playlist": "the videos in your playlist",
            "reel": "your reel"}.get(c["object"], "your content")
    return f"""Subject: Permission request to create short clips from {what}

Hi,

I run a small short-form channel and would like your permission to create
edited vertical clips from {what} ({c['url']}).

What I would do:
- Select moments, edit them (captions, framing, pacing) and publish them as
  short videos on: [PLATFORMS].
- Credit you in every post as: [ATTRIBUTION WORDING YOU PREFER].
- [Optional] Send each clip for your approval before it is published.

What I would not do:
- Re-upload full videos, imply that I am you, or use your content in ads.

Terms to agree:
- Scope: [all videos / specific videos] · Duration: [e.g. 12 months, revocable at any time]
- Revenue: [none / share of X%] · You can ask for any clip to be removed and I will remove it.

If you agree, a written reply confirming these terms is enough. You can revoke
it at any time.

Thanks,
[YOUR NAME]
"""
