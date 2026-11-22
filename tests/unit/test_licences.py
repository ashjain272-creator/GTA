"""Fails when an installed dependency has a copyleft or unknown licence not reviewed in docs/LICENCES.md."""
from __future__ import annotations

import importlib.metadata as md
import re
import tomllib
from pathlib import Path

LOCK = Path(__file__).resolve().parents[2] / "uv.lock"

# tqdm: MPL-2.0 AND MIT; certifi: MPL-2.0 (CA bundle data, unmodified). Both reviewed in docs/LICENCES.md.
REVIEWED_EXCEPTIONS = {"tqdm", "certifi", "clipops"}
COPYLEFT = re.compile(r"\b(A?GPL|LGPL|MPL|EUPL|CDDL|SSPL|CC-BY-NC|Commons Clause)", re.I)


def _licence(dist) -> str:
    m = dist.metadata
    lic = m.get("License-Expression") or (m.get("License") if m.get("License") and len(m.get("License")) < 80 else "")
    cls = [c.split("::")[-1].strip() for c in (m.get_all("Classifier") or []) if c.startswith("License ::")]
    return lic or "; ".join(cls)


def _norm(n: str) -> str:
    return re.sub(r"[-_.]+", "-", n).lower()


def test_no_unreviewed_copyleft_or_unknown_licences():
    """Checks the project's locked dependency closure only (not unrelated OS packages)."""
    locked = {_norm(p["name"]) for p in tomllib.loads(LOCK.read_text())["package"]}
    problems = []
    for d in md.distributions():
        name = d.metadata["Name"]
        if name is None or _norm(name) not in locked or name.lower() in REVIEWED_EXCEPTIONS:
            continue
        lic = _licence(d)
        if not lic or COPYLEFT.search(lic):
            problems.append(f"{name} {d.version}: {lic or 'UNKNOWN'}")
    assert problems == [], "review in docs/LICENCES.md: " + ", ".join(problems)
