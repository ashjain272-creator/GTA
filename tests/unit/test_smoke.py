"""Fast smoke tests (spec 2.3): run at the start of every session.

These assert repository state that later work depends on. Each test can fail.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from clipops import health

REPO = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.smoke


def test_master_prompt_conversion_kept_all_chapters():
    md = (REPO / "docs" / "MASTER_PROMPT.md").read_text()
    chapters = re.findall(r"^# Chapter (\d+)\.", md, re.M)
    appendices = re.findall(r"^# Appendix ([A-K])\.", md, re.M)
    assert [int(c) for c in chapters] == list(range(1, 19))
    assert sorted(set(appendices)) == list("ABCDEFGHIJK")


def test_master_prompt_docx_is_unmodified():
    import hashlib
    digest = hashlib.sha256((REPO / "docs" / "MASTER_PROMPT.docx").read_bytes()).hexdigest()
    assert digest == "97d729a0446957d2acebe943b3df1f333fa6b544909a5734142594e9bf35af68"


def test_required_docs_present_and_nonempty():
    missing = [c.name for c in health.run_checks(REPO) if c.name.startswith("doc:") and not c.ok]
    assert missing == []


def test_hardware_json_has_required_sections():
    hw = json.loads((REPO / "config" / "hardware.json").read_text())
    for key in ("role", "os", "cpu", "memory", "gpu", "ffmpeg", "storage", "software"):
        assert key in hw, key
    assert hw["role"] in {"operator-machine", "cloud-dev-container", "ci-runner", "other"}
    # every hardware encoder listed as compiled-in must have a recorded test outcome
    tested = {t["encoder"] for t in hw["ffmpeg"].get("encode_tests", [])}
    listed = {k for k, v in hw["ffmpeg"].get("encoders_of_interest", {}).items()
              if v and k.split("_")[-1] in {"nvenc", "qsv", "vaapi", "amf", "videotoolbox", "mf", "v4l2m2m"}}
    assert listed <= tested


def test_ledgers_have_entries():
    text = {n: (REPO / "docs" / n).read_text() for n in health.LEDGERS}
    assert re.search(r"^## ADR-\d{4}", text["DECISIONS.md"], re.M)
    assert re.search(r"^\| E-\d{3} ", text["EVIDENCE.md"], re.M)
    assert len(re.findall(r"^\| R\d{2} ", text["RISKS.md"], re.M)) >= 24
    assert re.search(r"^\| A-\d{3} ", text["ASSUMPTIONS.md"], re.M)
    assert "CHECKPOINT" in text["PROGRESS.md"]


def test_no_secret_material_committed():
    pattern = re.compile(r"(AIza[0-9A-Za-z_\-]{30,}|sk-ant-[0-9A-Za-z_\-]{20,}|-----BEGIN [A-Z ]*PRIVATE KEY-----)")
    offenders = []
    for p in REPO.rglob("*"):
        if p.is_file() and ".git" not in p.parts and p.suffix in {".py", ".md", ".json", ".yaml", ".yml", ".toml", ".txt"}:
            if pattern.search(p.read_text(errors="ignore")):
                offenders.append(str(p.relative_to(REPO)))
    assert offenders == []


def test_cli_health_exit_code_reflects_repo_state():
    from clipops.cli import main
    assert main(["health"]) == 0
