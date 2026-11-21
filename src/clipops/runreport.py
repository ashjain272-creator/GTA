"""Run report (spec A.5): every stage, warning, fallback and artefact of a run."""
from __future__ import annotations

import datetime as _dt
import json
import platform
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from . import __version__
from .config import config_hash
from .storage.artefacts import sha256_file, write_json


def _now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")


class StageFailed(RuntimeError):
    def __init__(self, code: str, klass: str, message: str):
        super().__init__(f"[{code}/{klass}] {message}")
        self.code, self.klass, self.message = code, klass, message


class RunReport:
    def __init__(self, cfg: dict, purpose: str):
        self.data: dict[str, Any] = {
            "run_id": "run_" + uuid.uuid4().hex[:12],
            "purpose": purpose,
            "started_at": _now(),
            "ended_at": None,
            "code_version": __version__,
            "config_hash": config_hash(cfg),
            "host": {"system": platform.system(), "machine": platform.machine(),
                     "python": platform.python_version()},
            "hardware_role": _hardware_role(cfg),
            "stages": [],
            "warnings": [],
            "fallbacks": [],
            "skipped": [],
            "artefacts": [],
            "models": {},
            "qa_summary": None,
            "publication_summary": "none: publishing not implemented (L0)",
            "operator_actions": [],
            "status": "running",
        }

    @contextmanager
    def stage(self, name: str) -> Iterator[dict]:
        rec: dict[str, Any] = {"name": name, "status": "running", "started_at": _now()}
        self.data["stages"].append(rec)
        t0 = time.perf_counter()
        try:
            yield rec
            if rec["status"] == "running":
                rec["status"] = "ok"
        except StageFailed as e:
            rec.update(status="failed", error={"code": e.code, "class": e.klass, "message": e.message})
            raise
        except Exception as e:
            rec.update(status="failed", error={"code": "unhandled", "class": "bug", "message": repr(e)})
            raise
        finally:
            rec["duration_s"] = round(time.perf_counter() - t0, 3)

    def warn(self, stage: str, code: str, message: str) -> None:
        self.data["warnings"].append({"stage": stage, "code": code, "message": message})

    def fallback(self, stage: str, from_: str, to: str, reason: str) -> None:
        """Spec 2.7: every fallback is structured, visible, and in the report."""
        self.data["fallbacks"].append({"stage": stage, "from": from_, "to": to, "reason": reason})
        self.warn(stage, "fallback", f"{from_} -> {to}: {reason}")

    def skip(self, stage: str, reason: str) -> None:
        self.data["skipped"].append({"stage": stage, "reason": reason})

    def artefact(self, kind: str, path: Path) -> None:
        self.data["artefacts"].append({"kind": kind, "path": str(path), "sha256": sha256_file(path),
                                       "bytes": path.stat().st_size})

    def operator_action(self, text: str) -> None:
        if text not in self.data["operator_actions"]:
            self.data["operator_actions"].append(text)

    def finish(self, out_dir: Path, status: str) -> Path:
        self.data["ended_at"] = _now()
        self.data["status"] = status
        return write_json(out_dir / f"{self.data['run_id']}.json", self.data)


def _hardware_role(cfg: dict) -> str | None:
    p = Path(cfg["_repo"]) / "config" / "hardware.json"
    try:
        return json.loads(p.read_text()).get("role")
    except (OSError, ValueError):
        return None
