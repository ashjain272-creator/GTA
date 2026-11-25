#!/usr/bin/env python3
"""Fetch the openly licensed test corpus (spec 2.9) and register each item with its licence.

Every item is public domain or Creative Commons, with the licence recorded in
config/grants/. Used for testing only; nothing here is published.
"""
from __future__ import annotations

import subprocess
import sys

CORPUS = [
    ("https://download.blender.org/demo/movies/ToS/tears_of_steel_720p.mov", "C", "tears_of_steel.json", None),
    ("https://upload.wikimedia.org/wikipedia/commons/8/84/AA33_Pipeline_AssaultDefend_Failed_20130123_720p.ogv", "C", "aa33_pipeline_pd.json", None),
    ("https://upload.wikimedia.org/wikipedia/commons/b/b0/Dishonored_2_gameplay_clip.webm", "C", "dishonored2_clip.json", None),
    ("https://upload.wikimedia.org/wikipedia/commons/4/47/FEZ_trial_gameplay_HD.webm", "C", "fez_trial.json", None),
    ("https://upload.wikimedia.org/wikipedia/commons/6/65/America%27s_Army_2.5.0_-_Multiplayer_gameplay_montage.webm", "C", "americas_army_pd.json", None),
    ("https://archive.org/download/storagespaceandsmeltingtreesayumsepisode51080p/Storage%20Space%20and%20Smelting%20Trees%20-%20Ayums%20-%20Episode%205-1080p.mp4", "C", "ayums_ep5.json", "Luanti"),
    ("https://archive.org/download/xonotic-draena-vs-craven-downer/Xonotic%20-%20Duel%20-%20Draena%20vs%20MxCraven%20on%20Downer-v1199654406.mp4", "C", "xonotic_duel.json", "Xonotic"),
    ("https://archive.org/download/discoveries-veloren/Discoveries_%20Veloren%21.mp4", "C", "veloren_discoveries.json", "Veloren"),
]


def main() -> int:
    rc = 0
    for url, klass, grant, game in CORPUS:
        cmd = [sys.executable, "-m", "clipops.cli", "source", "add", url, "--declare-rights", klass,
               "--grant", f"config/grants/{grant}"] + (["--game", game] if game else [])
        p = subprocess.run(cmd, capture_output=True, text=True)
        print(url.rsplit("/", 1)[-1], "->", (p.stdout.strip().splitlines() or [p.stderr.strip()[-200:]])[-1][:200])
        rc |= p.returncode
    return rc


if __name__ == "__main__":
    sys.exit(main())
