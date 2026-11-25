#!/usr/bin/env python3
"""One command: link (or local file) → finished, QA-checked vertical shorts in ./out/.

Examples:
  python scripts/clip_url.py "https://www.youtube.com/watch?v=..." --rights E --attest "test only, not for posting"
  python scripts/clip_url.py ~/Movies/my_gta_session.mp4 --rights A --game "Grand Theft Auto VI"

Each short is copied to out/<source>/ with a summary.json (style, hook, QA result,
reasons). Nothing is posted anywhere.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

from clipops import config
from clipops.ingest.rights import RightsRefused
from clipops.orchestrator.pipeline import Pipeline
from clipops.runreport import RunReport, StageFailed


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("source", help="YouTube/direct URL or local video file")
    ap.add_argument("--rights", default="A", choices=list("ABCE"),
                    help="A own footage, B creator permission (needs --grant), C licensed (needs --grant), E none (needs --attest)")
    ap.add_argument("--attest", help="class E: your stated basis (recorded as your responsibility)")
    ap.add_argument("--grant", help="JSON grant/licence file for class B/C")
    ap.add_argument("--game", default=None)
    ap.add_argument("--max", type=int, default=5, help="maximum number of shorts")
    ap.add_argument("--out", default="out")
    ap.add_argument("--include-weak", action="store_true", help="also keep shorts the machine review calls weak")
    a = ap.parse_args()
    cfg = config.load()
    rep = RunReport(cfg, f"clip_url {a.source}")
    p = Pipeline(cfg, rep)
    grant = json.loads(Path(a.grant).read_text()) if a.grant else None
    try:
        if a.source.startswith(("http://", "https://")):
            sids = p.add_url(a.source, a.rights, game=a.game, grant=grant, attestation=a.attest)
        else:
            sids = [p.add_source(Path(a.source).expanduser(), a.rights, game=a.game, grant=grant, attestation=a.attest)]
    except (StageFailed, RightsRefused) as e:
        print(f"Could not get the video: {e}")
        if "bot" in str(e).lower():
            print("YouTube asked for a bot check. Run this on your own computer/home connection, or export a cookie\n"
                  "file from a spare YouTube account and set CLIPOPS_YOUTUBE_COOKIES_FILE to its path.")
        rep.finish(Path(cfg["_repo"]) / "data" / "reports", "failed")
        return 2
    made = []
    for sid in sids:
        out = Path(a.out) / sid
        out.mkdir(parents=True, exist_ok=True)
        cands = [c for c in p.candidates(sid)["candidates"] if c["status"] == "proposed"][: a.max]
        if not cands:
            print(f"{sid}: no moment met the quality bar; nothing made (publishing nothing is acceptable).")
        for c in cands:
            try:
                plan = p.plan(sid, c["candidate_id"])
                info, qa = p.render_and_qa(sid, plan)
            except StageFailed as e:
                print(f"{c['candidate_id']}: failed: {e}")
                continue
            if not qa["passed"]:
                print(f"{info['short_id']}: rejected by QA ({', '.join(qa['failed'])})")
                continue
            mr = qa.get("creative_review_machine") or {}
            if mr.get("verdict") == "weak" and not a.include_weak:
                print(f"{info['short_id']}: held back, machine review says weak ({'; '.join(mr.get('weaknesses', []))})")
                continue
            dst = out / Path(info["path"]).name
            shutil.copy2(info["path"], dst)
            made.append({"file": str(dst), "from_s": c["boundaries"]["start_us"] / 1e6,
                         "to_s": c["boundaries"]["end_us"] / 1e6, "style": plan["style"]["name"],
                         "why_style": plan["style"]["selected_because"], "hook": plan["hook"]["text"],
                         "structure": plan["structure"]["name"], "framing": plan["framing"]["layout"],
                         "needs_review": qa["review_flags"], "brand_safety": plan["brand_safety"],
                         "machine_review": {k: mr.get(k) for k in ("overall", "verdict", "weaknesses")}})
            print(f"made {dst}  [{plan['style']['name']}]")
        (out / "summary.json").write_text(json.dumps(made, indent=2))
    rep.finish(Path(cfg["_repo"]) / "data" / "reports", "ok")
    print(f"\n{len(made)} short(s) in {Path(a.out).resolve()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
