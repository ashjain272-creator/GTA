"""Publish gate (spec 11.7), evaluated offline. It decides readiness and lists
every reason something is not ready. It never contacts a platform.

Checks run in the spec's order. Any failure means not ready. Results are
recorded either way.
"""
from __future__ import annotations

from pathlib import Path

from ..ingest import rights as rights_mod
from ..storage.artefacts import sha256_file


def evaluate(cfg: dict, src_dir: Path, plan: dict, render_info: dict, qa: dict, platform: str,
             profile: dict) -> dict:
    checks = []

    def add(name, ok, reason):
        checks.append({"name": name, "passed": bool(ok), "reason": reason})

    try:
        rec = rights_mod.gate(Path(cfg["_repo"]), src_dir, cfg["rights"]["allowed_production_classes"])
        scope = ((rec.get("grant") or {}).get("scope") or {}).get("platforms")
        ok = rec["class"] == "A" or not scope or platform in scope
        add("rights", ok, f"class {rec['class']}" + ("" if ok else f"; grant scope {scope} excludes {platform}"))
    except rights_mod.RightsRefused as e:
        rec = None
        add("rights", False, str(e))
    add("qa_passed", qa.get("passed"), "objective QA " + ("passed" if qa.get("passed") else f"failed: {qa.get('failed')}"))
    path = Path(render_info["path"])
    hash_ok = path.is_file() and qa.get("render_sha256") in (None, sha256_file(path))
    add("qa_hash_match", hash_ok, "render file unchanged since QA" if hash_ok else "render missing or modified after QA")
    review = qa.get("review_flags") or []
    add("human_review", not review, "no open review flags" if not review else f"needs operator review: {review}")
    add("creative_review", "not performed" not in str(qa.get("creative_review", "not performed")),
        str(qa.get("creative_review")))
    contrib = plan.get("contribution") or []
    add("contribution_test", len(contrib) >= 2,
        f"{len(contrib)} documented contributions (spec 4.7 requires >= 2; AM-27)")
    dur = plan["duration_us"] / 1e6
    add("duration", dur <= profile["export"]["max_duration_s"],
        f"{dur:.1f}s vs max {profile['export']['max_duration_s']}s for {platform}")
    lvl = cfg["publishing"]["platforms"].get(platform, {}).get("autonomy_level", "L0")
    add("autonomy", True, f"level {lvl}: " + ("bundle only, operator posts manually" if lvl == "L0" else "API upload as private/draft"))
    monet = rec["monetisation_allowed"] if rec else "unknown"
    ready = all(c["passed"] for c in checks)
    return {"platform": platform, "ready": ready, "autonomy_level": lvl, "monetisation_allowed": monet,
            "checks": checks, "blocking": [c["name"] for c in checks if not c["passed"]]}
