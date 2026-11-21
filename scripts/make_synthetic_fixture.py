#!/usr/bin/env python3
"""Generate a licence-clean synthetic 'gameplay' fixture with known ground truth.

Origin and licence: every element is generated locally. Video comes from FFmpeg
test sources, the noise bed and impact from FFmpeg's anoisesrc (seeded, so it is
deterministic), and speech from espeak-ng text-to-speech of lines written for
this project. No third-party footage, music or game assets are used.
[ASSUMPTION A-012: espeak-ng output audio carries no licence encumbrance.]

What it is good for: exercising pipeline mechanics and catching integration
breakage. What it is NOT good for: any quality claim. TTS on a clean bed is far
easier than real gaming audio (spec 2.9; AMENDMENTS AM-09).

Usage: python scripts/make_synthetic_fixture.py OUT.mp4 [--truth OUT.json]
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

DURATION = 36.0
# (start_s, text): the "moment" is the jump set-up (2 s), the impact (9.5 s),
# the reaction (10.5 s) and the verdict (14 s). Later lines are low-energy filler.
LINES = [
    (2.0, "Okay, watch this. I am going to jump the car over the bridge."),
    (7.0, "Here we go."),
    (10.5, "No way! That actually worked."),
    (14.0, "That was the best jump I have ever done."),
    (24.0, "Alright, let me find another car."),
    (29.0, "This one looks pretty slow."),
]
IMPACT_AT = 9.5


def sh(cmd: list[str]) -> None:
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        sys.exit(f"command failed: {' '.join(cmd[:3])}...\n{p.stderr[-800:]}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--truth")
    args = ap.parse_args()
    for tool in ("ffmpeg", "espeak-ng"):
        if not shutil.which(tool):
            sys.exit(f"{tool} is required (apt install {tool} / brew install {tool})")
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as td:
        tdp = Path(td)
        inputs, filters, labels = [], [], []
        for i, (t, text) in enumerate(LINES):
            wav = tdp / f"l{i}.wav"
            sh(["espeak-ng", "-v", "en-us", "-s", "150", "-a", "160", "-w", str(wav), text])
            inputs += ["-i", str(wav)]
            ms = int(t * 1000)
            filters.append(f"[{i}:a]aresample=48000,adelay={ms}|{ms},apad=whole_dur={DURATION}[v{i}]")
            labels.append(f"[v{i}]")
        n = len(LINES)
        # game-like bed (brown noise, quiet) and an impact burst
        inputs += ["-f", "lavfi", "-i", f"anoisesrc=d={DURATION}:c=brown:a=0.04:seed=7:r=48000",
                   "-f", "lavfi", "-i", f"anoisesrc=d=0.9:c=white:a=0.9:seed=11:r=48000"]
        ims = int(IMPACT_AT * 1000)
        filters.append(f"[{n + 1}:a]lowpass=f=900,afade=t=out:st=0.05:d=0.85,adelay={ims}|{ims},"
                       f"apad=whole_dur={DURATION}[imp]")
        filters.append(f"{''.join(labels)}[{n}:a][imp]amix=inputs={n + 2}:normalize=0,"
                       f"atrim=0:{DURATION},aformat=channel_layouts=stereo[a]")
        # video: moving test pattern, hard cut to a different scene at the impact
        inputs += ["-f", "lavfi", "-i", f"testsrc2=s=1280x720:r=30:d={IMPACT_AT}",
                   "-f", "lavfi", "-i", f"testsrc=s=1280x720:r=30:d={DURATION - IMPACT_AT}"]
        filters.append(f"[{n + 2}:v][{n + 3}:v]concat=n=2:v=1:a=0,format=yuv420p[v]")
        sh(["ffmpeg", "-hide_banner", "-y", *inputs, "-filter_complex", ";".join(filters),
            "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
            "-c:a", "aac", "-b:a", "160k", "-t", str(DURATION), str(out)])
    truth = {"fixture": out.name, "duration_s": DURATION, "generator": "scripts/make_synthetic_fixture.py",
             "lines": [{"start_s": t, "text": s} for t, s in LINES], "impact_s": IMPACT_AT,
             "scene_cut_s": IMPACT_AT,
             "expected_best_moment_s": [LINES[0][0], LINES[3][0] + 3.0],
             "licence": "generated locally; see module docstring"}
    if args.truth:
        Path(args.truth).write_text(json.dumps(truth, indent=2) + "\n")
    print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
