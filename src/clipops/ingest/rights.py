"""Rights records and the rights gate (spec 4.3, 4.14).

Fails closed: missing, invalid, class E or class F records never pass.
"""
from __future__ import annotations

import datetime as _dt
import json
from pathlib import Path

import jsonschema
import yaml

from ..storage.artefacts import read_json, sha256_file, write_json

PRODUCTION_CLASSES_MAX = {"A", "B", "C"}   # spec 4.3; D only via platform's own feature
REFUSED = {"E": "class E (unverified public): metadata-level research only, no acquisition (spec 4.3)",
           "F": "class F (prohibited): refused (spec 4.3)"}


class RightsRefused(Exception):
    pass


def _schema(repo: Path) -> dict:
    return json.loads((repo / "schemas" / "rights_record.schema.json").read_text())


def source_id_for(path: Path) -> tuple[str, str]:
    digest = sha256_file(path)
    return "src_" + digest[:16], digest


def game_policy_entries(repo: Path, game: str | None) -> list[dict]:
    if not game:
        return []
    reg = yaml.safe_load((repo / "config" / "game_policies.yaml").read_text()) or {}
    for key, entry in reg.items():
        if any(game.lower() in t.lower() or t.lower() in game.lower() for t in entry.get("titles", [])):
            return [{"game": game, "policy_ref": f"config/game_policies.yaml#{key}",
                     "policy_checked": entry["policy_checked"], "risk": entry.get("risk", "medium"),
                     "_monetisation_permitted": entry.get("monetisation_permitted", False)}]
    return [{"game": game, "policy_ref": None, "policy_checked": "never", "risk": "high",
             "_monetisation_permitted": None}]


def build_record(repo: Path, path: Path, klass: str, *, game: str | None = None,
                 grant: dict | None = None, synthetic: bool = False, notes: str | None = None,
                 platform: str = "file", origin_url: str | None = None) -> dict:
    if klass in REFUSED:
        raise RightsRefused(REFUSED[klass])
    sid, digest = source_id_for(path)
    today = _dt.date.today().isoformat()
    policies = game_policy_entries(repo, game)
    monet = "unknown"
    if synthetic:
        monet = "no"
    elif policies and any(p["_monetisation_permitted"] is False for p in policies):
        monet = "no"
    elif policies and all(p["_monetisation_permitted"] for p in policies) and klass == "A":
        monet = "yes"
    rec = {
        "source_id": sid, "platform": platform, "origin_url": origin_url, "origin_path": str(path),
        "sha256": digest, "class": klass, "owner_declared_by_operator": klass == "A",
        "owner_verified_by_oauth": False, "grant": grant,
        "game_policies": [{k: v for k, v in p.items() if not k.startswith("_")} for p in policies],
        "third_party_content_flags": [], "monetisation_allowed": monet,
        "synthetic_fixture": synthetic, "created_at": today, "last_reviewed": today, "notes": notes,
    }
    jsonschema.validate(rec, _schema(repo))
    return rec


def save_record(rec: dict, src_dir: Path) -> Path:
    return write_json(src_dir / "rights.json", rec)


def gate(repo: Path, src_dir: Path, allowed: list[str]) -> dict:
    """Return the validated record or raise RightsRefused. Fails closed."""
    p = src_dir / "rights.json"
    if not p.is_file():
        raise RightsRefused("no rights record: register the source with `clipops source add`")
    rec = read_json(p)
    try:
        jsonschema.validate(rec, _schema(repo))
    except jsonschema.ValidationError as e:
        raise RightsRefused(f"rights record invalid: {e.message}") from e
    if rec["class"] in REFUSED:
        raise RightsRefused(REFUSED[rec["class"]])
    if rec["class"] not in set(allowed) & PRODUCTION_CLASSES_MAX:
        raise RightsRefused(f"class {rec['class']} not in allowed production classes {allowed}")
    exp = (rec.get("grant") or {}).get("expires")
    if exp and exp < _dt.date.today().isoformat():
        raise RightsRefused(f"grant expired on {exp}")
    return rec
