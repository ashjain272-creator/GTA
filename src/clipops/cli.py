"""Command-line entry point. Only implemented commands are registered (ADR-0004)."""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import shutil
import subprocess
import sys
from pathlib import Path

from . import __version__, config, health
from .ingest.rights import RightsRefused
from .runreport import RunReport, StageFailed
from .storage.artefacts import read_json, write_json


def _find(cfg: dict, pattern: str) -> Path:
    hits = sorted(config.data_path(cfg, "work").glob(pattern))
    if not hits:
        raise SystemExit(f"not found: {pattern}")
    return hits[0]


def _run(cfg: dict, purpose: str, fn) -> int:
    from .orchestrator.pipeline import Pipeline
    rep = RunReport(cfg, purpose)
    reports = Path(cfg["_repo"]) / "data" / "reports"
    status, code = "ok", 0
    try:
        result = fn(Pipeline(cfg, rep), rep)
        if result is not None:
            print(json.dumps(result, indent=2, default=str)[:4000])
        if rep.data.get("qa_summary") and not rep.data["qa_summary"]["passed"]:
            status, code = "qa_failed", 1
    except RightsRefused as e:
        rep.warn("rights", "refused", str(e))
        rep.operator_action(f"Rights: {e}")
        print(f"REFUSED: {e}", file=sys.stderr)
        status, code = "refused", 3
    except StageFailed as e:
        print(f"FAILED: {e}", file=sys.stderr)
        status, code = "failed", 2
    path = rep.finish(reports, status)
    print(f"run report: {path}", file=sys.stderr)
    return code


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="clipops")
    ap.add_argument("--version", action="version", version=__version__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    h = sub.add_parser("health", help="check repository and host state")
    h.add_argument("--json", action="store_true")

    src = sub.add_parser("source").add_subparsers(dest="sub", required=True)
    sa = src.add_parser("add", help="register a local file with a declared rights class")
    sa.add_argument("path")
    sa.add_argument("--declare-rights", required=True, choices=list("ABCDEF"))
    sa.add_argument("--grant", help="JSON file with grant details (required for class B/C)")
    sa.add_argument("--game")
    sa.add_argument("--notes")

    sc = src.add_parser("classify", help="classify a URL; never downloads (class E path, spec 4.4)")
    sc.add_argument("url")

    for group, verb in (("ingest", "run"), ("analyse", "run"), ("candidates", "generate")):
        g = sub.add_parser(group).add_subparsers(dest="sub", required=True)
        g.add_parser(verb).add_argument("source_id")

    pl = sub.add_parser("plan").add_subparsers(dest="sub", required=True)
    pm = pl.add_parser("make")
    pm.add_argument("candidate_id")

    rd = sub.add_parser("render").add_subparsers(dest="sub", required=True)
    rr = rd.add_parser("run", help="render a plan, then run objective QA on the output")
    rr.add_argument("plan_id")

    qa = sub.add_parser("qa").add_subparsers(dest="sub", required=True)
    qa.add_parser("run").add_argument("short_id")

    dm = sub.add_parser("demo").add_subparsers(dest="sub", required=True)
    dr = dm.add_parser("run", help="walking-skeleton demonstration on a synthetic fixture")
    dr.add_argument("--out", default=None, help="directory for the recorded demo output")

    args = ap.parse_args(argv)
    if args.cmd == "health":
        return health.main(as_json=args.json)

    cfg = config.load()
    if args.cmd == "source" and args.sub == "classify":
        from .ingest.classify import class_e_outcome
        out = class_e_outcome(args.url)
        stamp = _dt.datetime.now(_dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        path = write_json(Path(cfg["_repo"]) / "data" / "reports" / f"classify_{stamp}.json", out)
        print(json.dumps(out["classification"], indent=2))
        print("\n" + out["limitation"] + "\n\n--- permission request draft ---\n" + out["permission_request_draft"])
        print(f"record: {path}", file=sys.stderr)
        return 0
    if args.cmd == "source":
        grant = json.loads(Path(args.grant).read_text()) if args.grant else None
        return _run(cfg, "source add", lambda p, r: {"source_id": p.add_source(
            Path(args.path), args.declare_rights, game=args.game, grant=grant, notes=args.notes)})
    if args.cmd == "ingest":
        return _run(cfg, "ingest", lambda p, r: p.ingest(args.source_id))
    if args.cmd == "analyse":
        return _run(cfg, "analyse", lambda p, r: {k: {"_input_key": v.get("_input_key")}
                                                    for k, v in p.analyse(args.source_id).items()})
    if args.cmd == "candidates":
        def cands(p, r):
            res = p.candidates(args.source_id)
            return [{"id": c["candidate_id"], "status": c["status"], "viability": c["overall"]["viability"],
                     "start_s": c["boundaries"]["start_us"] / 1e6, "end_s": c["boundaries"]["end_us"] / 1e6,
                     "rejection_reason": c["rejection_reason"]} for c in res["candidates"]]
        return _run(cfg, "candidates", cands)
    if args.cmd == "plan":
        source_id = "src_" + args.candidate_id.split("_")[1]
        src_dir = _find(cfg, f"{source_id}*")
        return _run(cfg, "plan", lambda p, r: p.plan(src_dir.name, args.candidate_id))
    if args.cmd == "render":
        plan_path = _find(cfg, f"*/plans/{args.plan_id}.json")
        plan = read_json(plan_path)
        return _run(cfg, "render", lambda p, r: p.render_and_qa(plan["source_id"], plan)[1])
    if args.cmd == "qa":
        info_path = _find(cfg, f"*/renders/{args.short_id}.json")
        info = read_json(info_path)
        plan = read_json(_find(cfg, f"*/plans/{info['plan_id']}.json"))

        def rerun_qa(p, r):
            from .qa.checks import run_qa
            with r.stage("qa"):
                res = run_qa(info, plan, cfg, info_path.parent.parent / "qa")
            write_json(info_path.parent.parent / "qa" / f"{args.short_id}.json", res)
            r.data["qa_summary"] = {"short_id": res["short_id"], "passed": res["passed"],
                                    "failed": res["failed"], "review_flags": res["review_flags"], "publishable": res["publishable"]}
            return res
        return _run(cfg, "qa", rerun_qa)
    if args.cmd == "demo":
        from .demo import run_demo
        return run_demo(cfg, Path(args.out) if args.out else None)
    return 2


if __name__ == "__main__":
    sys.exit(main())
