"""`clipops health`: verifies the repository and host are in a known state."""
from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass, asdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

LEDGERS = ["DECISIONS.md", "EVIDENCE.md", "RISKS.md", "ASSUMPTIONS.md", "PROGRESS.md"]
REQUIRED_DOCS = LEDGERS + [
    "MASTER_PROMPT.docx", "MASTER_PROMPT.md", "AMENDMENTS.md", "HARDWARE_REPORT.md",
    "KNOWLEDGE_MAP.md", "DISCOVERY.md", "BLOCKERS.md", "OPERATOR_TODO.md", "ROADMAP.md",
    "PLATFORM_LIMITS.md",
]


@dataclass
class Check:
    name: str
    ok: bool
    detail: str


def _tool(name: str) -> Check:
    path = shutil.which(name)
    if not path:
        return Check(f"tool:{name}", False, "not on PATH")
    out = subprocess.run([name, "-hide_banner", "-version"], capture_output=True, text=True)
    return Check(f"tool:{name}", out.returncode == 0, out.stdout.splitlines()[0] if out.stdout else path)


def run_checks(repo: Path = REPO) -> list[Check]:
    checks: list[Check] = []
    for doc in REQUIRED_DOCS:
        p = repo / "docs" / doc
        checks.append(Check(f"doc:{doc}", p.is_file() and p.stat().st_size > 0,
                            "present" if p.is_file() else "missing"))
    hw = repo / "config" / "hardware.json"
    if hw.is_file():
        data = json.loads(hw.read_text())
        role = data.get("role")
        checks.append(Check("hardware.json", True, f"role={role}"))
        checks.append(Check("hardware:operator-machine-inspected", role == "operator-machine",
                            "operator machine inspected" if role == "operator-machine"
                            else f"only '{role}' inspected; see BLOCKERS.md B-01"))
    else:
        checks.append(Check("hardware.json", False, "missing; run scripts/inspect_hardware.py"))
    checks += [_tool("ffmpeg"), _tool("ffprobe")]
    return checks


def main(as_json: bool = False) -> int:
    checks = run_checks()
    if as_json:
        print(json.dumps([asdict(c) for c in checks], indent=2))
    else:
        for c in checks:
            print(f"[{'ok' if c.ok else '!!'}] {c.name}: {c.detail}")
    # Missing operator-machine inspection is a known blocker, not a broken repo.
    hard = [c for c in checks if not c.ok and c.name != "hardware:operator-machine-inspected"]
    return 1 if hard else 0
