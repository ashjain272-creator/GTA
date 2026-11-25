#!/usr/bin/env python3
"""Plan, render and QA every proposed candidate of a source; write contact sheets for review.

Usage: python scripts/render_candidates.py <source_id> [--out DIR] [--style NAME]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from clipops import config
from clipops.media import run
from clipops.orchestrator.pipeline import Pipeline
from clipops.runreport import RunReport, StageFailed


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("source_id")
    ap.add_argument("--out", default="data/review")
    ap.add_argument("--style")
    ap.add_argument("--limit", type=int, default=10)
    a = ap.parse_args()
    cfg = config.load()
    rep = RunReport(cfg, f"render candidates {a.source_id}")
    p = Pipeline(cfg, rep)
    out = Path(a.out) / a.source_id
    out.mkdir(parents=True, exist_ok=True)
    cands = [c for c in p.candidates(a.source_id)["candidates"] if c["status"] == "proposed"][: a.limit]
    rows = []
    for c in cands:
        try:
            plan = p.plan(a.source_id, c["candidate_id"], style=a.style)
            info, qa = p.render_and_qa(a.source_id, plan)
        except StageFailed as e:
            rows.append({"candidate": c["candidate_id"], "error": str(e)})
            print(c["candidate_id"], "FAILED", e)
            continue
        sheet = out / f"{info['short_id']}.png"
        run(["ffmpeg", "-v", "error", "-y", "-i", info["path"], "-vf",
             "fps=1/1.5,scale=180:320,tile=8x2", "-frames:v", "1", str(sheet)])
        row = {"candidate": c["candidate_id"], "short": info["path"], "sheet": str(sheet),
               "window_s": [c["boundaries"]["start_us"] / 1e6, c["boundaries"]["end_us"] / 1e6],
               "style": plan["style"]["name"], "layout": plan["framing"]["layout"], "framing_reason": plan["framing"]["reason"],
               "structure": plan["structure"]["name"], "hook": plan["hook"]["text"], "zooms": len(plan["zooms"]),
               "sfx": [e["asset"] for e in plan["sfx"]], "qa_passed": qa["passed"], "qa_failed": qa["failed"],
               "review": qa["review_flags"], "duration_s": plan["duration_us"] / 1e6,
               "machine_review": {k: (qa.get("creative_review_machine") or {}).get(k) for k in ("overall", "verdict", "weaknesses")}}
        rows.append(row)
        print(json.dumps(row))
    (out / "summary.json").write_text(json.dumps(rows, indent=2))
    rep.finish(Path(cfg["_repo"]) / "data" / "reports", "ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
