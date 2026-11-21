#!/usr/bin/env python3
"""Record presence or absence of platform credentials without reading values.

Spec section 2.2 step 4. Only environment-variable NAMES and file EXISTENCE are
inspected; no value is printed, logged, hashed or written. Output is a JSON
document suitable for docs/ and for the run report.

The names below are this project's conventions (see config/settings.example.yaml),
not names any platform mandates.
"""
from __future__ import annotations

import datetime as _dt
import json
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

EXPECTED = {
    "youtube": ["CLIPOPS_YOUTUBE_CLIENT_SECRETS_FILE", "CLIPOPS_YOUTUBE_TOKEN_FILE"],
    "tiktok": ["CLIPOPS_TIKTOK_CLIENT_KEY", "CLIPOPS_TIKTOK_CLIENT_SECRET"],
    "instagram": ["CLIPOPS_META_APP_ID", "CLIPOPS_META_APP_SECRET", "CLIPOPS_IG_USER_ID"],
    "twitch": ["CLIPOPS_TWITCH_CLIENT_ID", "CLIPOPS_TWITCH_CLIENT_SECRET"],
    "hosted_llm_optional": ["ANTHROPIC_API_KEY"],
}
FILE_VARS = {"CLIPOPS_YOUTUBE_CLIENT_SECRETS_FILE", "CLIPOPS_YOUTUBE_TOKEN_FILE"}
SECRET_DIRS = [REPO / "secrets", Path.home() / ".config" / "clipops"]


def main() -> int:
    report: dict = {
        "generated_at": _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds"),
        "method": "env var name presence and file existence only; values never read",
        "platforms": {},
        "secret_dirs": {str(d): d.is_dir() for d in SECRET_DIRS},
    }
    for platform_name, names in EXPECTED.items():
        entry = {}
        for n in names:
            present = bool(os.environ.get(n))
            if present and n in FILE_VARS:
                entry[n] = "present_file_exists" if Path(os.environ[n]).is_file() else "present_file_missing"
            else:
                entry[n] = "present" if present else "absent"
        report["platforms"][platform_name] = entry
    out = json.dumps(report, indent=2)
    if len(sys.argv) > 1:
        Path(sys.argv[1]).write_text(out + "\n")
    print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
