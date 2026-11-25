"""Contextual style selection (spec 8.6, Appendix B.8).

fit(style, moment) = tone/feature match - recency penalty, subject to hard
exclusions (style unavailable, flash risk, missing assets). Every choice
records its reasons, the runner-up, and the scores of all styles, so a
reviewer can see why. No rotation, no randomness.
"""
from __future__ import annotations

import json
from pathlib import Path

import yaml


def load_styles(repo: Path) -> dict:
    data = yaml.safe_load((repo / "config" / "styles.yaml").read_text())
    return {k: v for k, v in data.items() if k != "defaults"}


def moment_profile(candidate: dict, events: dict | None) -> dict:
    """Normalised features (0..1) describing the moment, from the candidate and audio events."""
    s = candidate["scores"]
    b = candidate["boundaries"]
    frames = [f for f in (events or {}).get("frames", []) if b["start_us"] <= f["t_us"] <= b["end_us"]]

    def peak(k):
        return max((f.get(k, 0.0) for f in frames), default=0.0)

    speech_share = (sum(1 for f in frames if f.get("speech", 0) >= 0.5) / len(frames)) if frames else 0.0
    impact = max(peak("explosion"), peak("gunshot"), peak("crash"))
    humor = min(1.0, peak("laughter") * 1.5 + 0.35 * s.get("hook", {}).get("value", 0.0)
                + (0.25 if candidate.get("signals", {}).get("exclamations", 0) >= 2 else 0.0))
    energy = min(1.0, 0.6 * s["emotional_intensity"]["value"] + 0.4 * max(impact, peak("scream")))
    return {"energy": round(energy, 3), "humor": round(humor, 3), "dialogue": round(speech_share, 3),
            "impact": round(impact, 3), "calm": round(1.0 - energy, 3)}


def _closeness(rng: list[float], x: float) -> float:
    lo, hi = rng
    if lo <= x <= hi:
        return 1.0
    d = lo - x if x < lo else x - hi
    return max(0.0, 1.0 - 2.5 * d)


def fit(style: dict, prof: dict) -> tuple[float, list[str]]:
    w = style["fit"]
    parts = {"energy": 1.2 * _closeness(w["energy"], prof["energy"])}
    for k in ("humor", "dialogue", "impact", "calm"):
        parts[k] = w[k] * prof[k]
    score = sum(parts.values())
    top = sorted(parts.items(), key=lambda kv: -abs(kv[1]))[:2]
    reasons = [f"{k}={prof[k] if k != 'energy' else prof['energy']} contributes {v:+.2f}" for k, v in top]
    return round(score, 3), reasons


def history(repo: Path, cfg: dict) -> list[str]:
    p = Path(cfg["_repo"]) / "data" / "db" / "style_history.json"
    try:
        return json.loads(p.read_text())[-20:]
    except (OSError, ValueError):
        return []


def record_choice(cfg: dict, style_name: str) -> None:
    p = Path(cfg["_repo"]) / "data" / "db" / "style_history.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    h = history(Path(cfg["_repo"]), cfg) + [style_name]
    p.write_text(json.dumps(h[-50:]))


def select_style(repo: Path, cfg: dict, prof: dict, *, flash_risk: bool = False,
                 recent: list[str] | None = None, force: str | None = None) -> dict:
    styles = load_styles(repo)
    recent = recent if recent is not None else history(repo, cfg)
    table, excluded = [], []
    for name, st in styles.items():
        if not st.get("available", True):
            excluded.append({"style": name, "reason": st.get("unavailable_reason", "unavailable")})
            continue
        if flash_risk and st["zoom"]["max_per_10s"] >= 3:
            excluded.append({"style": name, "reason": "flash risk in source: fast-cut styles excluded"})
            continue
        score, reasons = fit(st, prof)
        share = recent.count(name) / len(recent) if recent else 0.0
        penalty = round(1.5 * max(0.0, share - 0.4), 3)      # diversity: penalise styles above 40% recent share
        if penalty:
            reasons.append(f"recent overuse {share:.0%} → −{penalty}")
        table.append({"style": name, "score": round(score - penalty, 3), "reasons": reasons})
    table.sort(key=lambda r: -r["score"])
    if force:
        chosen = next((r for r in table if r["style"] == force), None)
        if chosen is None:
            raise ValueError(f"style {force!r} unavailable or excluded")
        chosen = dict(chosen, reasons=["forced by operator"] + chosen["reasons"])
    else:
        chosen = table[0]
    runner = next((r for r in table if r["style"] != chosen["style"]), None)
    return {"name": chosen["style"], "params": styles[chosen["style"]], "score": chosen["score"],
            "selected_because": chosen["reasons"], "runner_up": runner and runner["style"],
            "runner_up_reason": runner and f"scored {runner['score']} vs {chosen['score']}",
            "profile": prof, "all_scores": table, "excluded": excluded}
