"""Settings loader: settings.example.yaml defaults, overlaid by settings.yaml."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

import yaml

REPO = Path(__file__).resolve().parents[2]


def _merge(base: dict, over: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in over.items():
        out[k] = _merge(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else v
    return out


def load(repo: Path = REPO, overrides: dict | None = None) -> dict[str, Any]:
    cfg = yaml.safe_load((repo / "config" / "settings.example.yaml").read_text())
    local = repo / "config" / "settings.yaml"
    if local.is_file():
        cfg = _merge(cfg, yaml.safe_load(local.read_text()) or {})
    if overrides:
        cfg = _merge(cfg, overrides)
    cfg["_repo"] = str(repo)
    return cfg


def config_hash(cfg: dict) -> str:
    clean = {k: v for k, v in cfg.items() if not k.startswith("_")}
    return hashlib.sha256(json.dumps(clean, sort_keys=True).encode()).hexdigest()[:16]


def data_path(cfg: dict, key: str) -> Path:
    p = Path(cfg["paths"][key])
    return p if p.is_absolute() else Path(cfg["_repo"]) / p
