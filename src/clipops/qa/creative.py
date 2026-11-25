"""Machine creative review: proxy scores for the Appendix C rubric (1-5), each with evidence.

Every score is derived from something measured in the plan or the QA checks;
nothing is guessed. It does NOT replace human creative review (the publish
gate still requires one). It ranks shorts, explains weaknesses and flags edits
that are not worth a human's time. Scores below 3 come with a reason, as
Appendix C asks.
"""
from __future__ import annotations


def _clamp(x: float) -> int:
    return int(max(1, min(5, round(x))))


def review(plan: dict, qa: dict, candidate: dict | None = None) -> dict:
    checks = {c["name"]: c for c in qa.get("checks", [])}
    cues = plan.get("subtitles", {}).get("cues", [])
    words = [w for c in cues for w in c.get("words", [])]
    sig = (candidate or {}).get("signals", {})
    dur = plan["duration_us"] / 1e6
    out: dict[str, dict] = {}

    # Hook: something happens in the first 2 s (speech, hook text, teaser, or an impact)
    early_speech = any(w["start_us"] < 2_000_000 for w in words)
    teaser = plan["structure"]["name"] == "cold_open"
    hook_text = bool(plan.get("hook", {}).get("text"))
    s = 2 + early_speech + teaser + hook_text
    out["hook"] = {"score": _clamp(s), "evidence": f"speech in first 2 s: {early_speech}; cold open: {teaser}; hook text: {hook_text}"}

    # Payoff: an impact and/or a reaction, placed after a build-up
    impact = sig.get("impact_score", 0.0)
    reaction = sig.get("reaction", 0.0)
    s = 1.5 + 2.0 * min(1.0, impact / 0.5) + 1.5 * min(1.0, reaction)
    out["payoff"] = {"score": _clamp(s), "evidence": f"impact {impact:.2f}, reaction {reaction:.2f}"}

    # Pacing: dead air and length
    gaps = [(b["start_us"] - a["end_us"]) / 1e6 for a, b in zip(words, words[1:])]
    longest = max(gaps, default=0.0) if words else 0.0
    # slow first beat: after any teaser, how long until the first word or the payoff?
    teaser_us = next(((s_["src_end_us"] - s_["src_start_us"]) for s_ in plan.get("timeline", []) if s_["role"] == "teaser"), 0)
    first_word = min((w["start_us"] for w in words if w["start_us"] >= teaser_us), default=None)
    main_start = next((s_["src_start_us"] for s_ in plan.get("timeline", []) if s_["role"] != "teaser"), None)
    pay = sig.get("payoff_us")
    pay_out = (teaser_us + pay - main_start) if (pay and main_start is not None and pay >= main_start) else None
    firsts = [t for t in (first_word, pay_out) if t is not None]
    slow = ((min(firsts) - teaser_us) / 1e6) if firsts else 0.0
    s = 5 - (longest > 2.0) - (longest > 3.0) - (dur > 45) - (dur < 8) - 2 * (slow > 6.0)
    out["pacing"] = {"score": _clamp(s), "evidence": f"duration {dur:.1f}s, longest pause {longest:.1f}s, "
                                                     f"first beat after {slow:.1f}s"}

    # Subtitles: accuracy proxy (cross-model agreement), reading speed, safe area
    if cues:
        verified = [w.get("verified", w.get("confidence", 0) >= 0.5) for w in words]
        agree = sum(verified) / max(len(verified), 1)
        m = checks.get("subtitle_reading_speed", {}).get("measured", 0) or 0
        cps = m.get("run_avg_max", 0) if isinstance(m, dict) else m
        s = 1 + 3 * agree + (cps <= 20) - (not checks.get("subtitle_safe_area", {}).get("passed", True))
        out["subtitles"] = {"score": _clamp(s), "evidence": f"word agreement {agree:.0%}, max {cps} chars/s"}
    else:
        out["subtitles"] = {"score": 3, "evidence": "no speech in clip; no captions needed"}

    # Audio
    li = checks.get("integrated_loudness", {}).get("measured")
    tp = checks.get("true_peak", {}).get("measured")
    ok = checks.get("integrated_loudness", {}).get("passed") and checks.get("true_peak", {}).get("passed")
    out["audio"] = {"score": 5 if ok else 2, "evidence": f"{li} LUFS, {tp} dBTP"}

    # Visual composition: framing decision quality
    fr = plan.get("framing", {})
    if fr.get("layout") == "tracked_crop":
        conc = fr.get("concentration") or 0
        s = 4 + (conc >= 0.7 or "crosshair" in fr.get("reason", "") or "third-person" in fr.get("reason", ""))
    else:
        s = 3                                   # whole frame kept: safe but small on a phone
    out["visual_composition"] = {"score": _clamp(s), "evidence": f"{fr.get('layout')}: {fr.get('reason', '')[:80]}"}

    # Ending: lands on a sentence end or a freeze; not mid-word
    last = words[-1]["text"] if words else ""
    clean_end = (not words) or last.rstrip()[-1:] in ".!?" or plan.get("freeze_end_us", 0) > 0
    out["ending"] = {"score": 4 if clean_end else 2, "evidence": f"last word '{last}', freeze {plan.get('freeze_end_us', 0) / 1e6:.1f}s"}

    # Originality and contribution
    n = len(plan.get("contribution", []))
    out["originality"] = {"score": _clamp(1 + 1.3 * n), "evidence": f"{n} documented contribution(s)"}

    # Integrity: hook is verbatim, captions masked if profane
    out["integrity"] = {"score": 5 if plan.get("hook", {}).get("source", "").startswith(("verbatim", "game")) or not hook_text else 3,
                        "evidence": plan.get("hook", {}).get("source", "no hook")}

    weights = {"hook": 2, "payoff": 2, "pacing": 1.5, "subtitles": 1.5, "audio": 1, "visual_composition": 1,
               "ending": 1, "originality": 1.5, "integrity": 1}
    overall = sum(out[k]["score"] * w for k, w in weights.items()) / sum(weights.values())
    weak = [f"{k}: {v['evidence']}" for k, v in out.items() if v["score"] < 3]
    return {"method": "machine proxy for Appendix C (not a substitute for human review)",
            "scores": out, "overall": round(overall, 2), "weaknesses": weak,
            "verdict": ("strong" if overall >= 4 and not weak            # strong means no rubric item below 3
                        else "acceptable" if overall >= 3.2 and len(weak) <= 2 else "weak")}
