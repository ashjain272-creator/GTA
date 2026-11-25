"""Edit plan (spec 8.2, A.2): a concrete, explainable edit for one candidate.

A style supplies the design language; the plan applies it to this moment's
own signals: where the payoff lands, where the stressed words are, whether
anyone is speaking. Every operation records why it exists. Output times are
microseconds on the short's own timeline.
"""
from __future__ import annotations

import re

from .hooks import EXCLAIM, make_hook

PUNCT_END = re.compile(r"[.!?,;:]$")
PROFANITY = re.compile(r"\b(fuck\w*|shit\w*|bitch\w*|cunt\w*|asshole\w*|motherfuck\w*|dick\w*|bastard\w*)\b", re.I)


def mask_profanity(text: str) -> str:
    """Brand safety (spec AM-20): keep the first letter, mask the rest ('f***')."""
    return PROFANITY.sub(lambda m: m.group(0)[0] + "*" * (len(m.group(0)) - 1), text)


# ----------------------------------------------------------------------------- timeline
def _words(transcript: dict, a: int, b: int) -> list[dict]:
    return [w for s in transcript.get("segments", []) for w in s["words"] if w["start_us"] >= a and w["end_us"] <= b]


def _overlaps_speech(words: list[dict], a: int, b: int, guard: int = 0) -> bool:
    return any(w["start_us"] < b + guard and w["end_us"] > a - guard for w in words)


def _snap_out_of_words(t: int, words: list[dict], direction: int) -> int:
    """Move a cut point so it never lands inside a word (direction -1 = earlier, +1 = later)."""
    for w in words:
        if w["start_us"] < t < w["end_us"]:
            return w["start_us"] if direction < 0 else w["end_us"]
    return t


def build_segments(cand: dict, words: list[dict], style: dict, cfg: dict) -> tuple[list[dict], list[str]]:
    S, E = cand["boundaries"]["start_us"], cand["boundaries"]["end_us"]
    sig = cand.get("signals", {})
    p = sig.get("payoff_us")
    notes: list[str] = []
    cap = int(cfg["edit"].get("max_silent_buildup_s", 5.0) * 1e6)
    if p and p - S > cap and not any(w["start_us"] < p - 1_000_000 for w in words if w["start_us"] >= S):
        notes.append(f"build-up trimmed from {(p - S) / 1e6:.1f}s to {cap / 1e6:.1f}s: no setup speech before the payoff")
        S = p - cap
    main = [{"src_start_us": S, "src_end_us": E, "speed": 1.0, "role": "main"}]
    ramp = style.get("speed_ramp", {})
    if ramp.get("enabled") and p and sig.get("impact_score", 0) >= 0.15:
        a, b = int(p - ramp["before_s"] * 1e6), int(p + ramp["after_s"] * 1e6)
        a, b = max(a, S), min(b, E)
        if _overlaps_speech(words, a, b):
            notes.append("speed ramp skipped: speech overlaps the impact window (slowed speech sounds wrong)")
        elif b - a > 200_000:
            main = [{"src_start_us": S, "src_end_us": a, "speed": 1.0, "role": "main"},
                    {"src_start_us": a, "src_end_us": b, "speed": ramp["factor"], "role": "ramp"},
                    {"src_start_us": b, "src_end_us": E, "speed": 1.0, "role": "main"}]
            notes.append(f"speed ramp x{ramp['factor']} on the impact at {p / 1e6:.2f}s (no speech in window)")
    segs = [m for m in main if m["src_end_us"] - m["src_start_us"] > 50_000]
    hook = style.get("hook", {})
    rel = (p - S) / max(E - S, 1) if p else 0.0
    if hook.get("cold_open_if_payoff_late") and p and rel > 0.4:
        e = cfg["edit"]
        ta = _snap_out_of_words(int(p - e["teaser_before_s"] * 1e6), words, -1)
        tb = _snap_out_of_words(int(p + e["teaser_after_s"] * 1e6), words, +1)
        # finish a reaction sentence that starts inside the teaser or within 0.4 s after it
        for i, w in enumerate(words):
            if ta < w["start_us"] <= tb + 400_000:
                j = i
                while j + 1 < len(words) and not re.search(r"[.!?]$", words[j]["text"]) \
                        and words[j + 1]["start_us"] - words[j]["end_us"] < 600_000:
                    j += 1
                nxt = words[j + 1]["start_us"] if j + 1 < len(words) else words[j]["end_us"] + 300_000
                tb = max(tb, words[j]["end_us"] + min(150_000, (nxt - words[j]["end_us"]) // 2))
                break
        tb = _snap_out_of_words(tb, words, -1)
        ta, tb = max(ta, S), min(tb, E)
        if 600_000 <= tb - ta <= 3_000_000:
            segs = [{"src_start_us": ta, "src_end_us": tb, "speed": 1.0, "role": "teaser"}] + segs
            notes.append(f"cold open: payoff at {rel:.0%} of the clip, teased first ({(tb - ta) / 1e6:.1f}s), then the build-up")
        else:
            notes.append("cold open skipped: teaser would be too short or cut speech")
    return segs, notes


def out_time_map(segs: list[dict]):
    """Return f(src_us, role_filter) → output µs, for times inside non-teaser segments."""
    spans, t = [], 0
    for s in segs:
        dur = int((s["src_end_us"] - s["src_start_us"]) / s["speed"])
        spans.append((s, t, dur))
        t += dur

    def f(src_us: int, include_teaser: bool = False) -> int | None:
        for s, o, _ in spans:
            if s["role"] == "teaser" and not include_teaser:
                continue
            if s["src_start_us"] <= src_us <= s["src_end_us"]:
                return o + int((src_us - s["src_start_us"]) / s["speed"])
        return None
    return f, t


# ----------------------------------------------------------------------------- captions
def caption_cues(words: list[dict], fmap, style: dict, scfg: dict) -> list[dict]:
    c = style["caption"]
    max_w = 3 if c["animation"] in ("pop_word", "karaoke") else scfg["max_words_per_cue"]
    max_us = int(scfg["max_cue_s"] * 1e6)
    mapped = []
    for w in words:
        a, b = fmap(w["start_us"]), fmap(w["end_us"])
        if a is None or b is None:
            continue
        text = w["text"].upper() if c["case"] == "upper" else w["text"]
        if scfg.get("mask_profanity", True):
            text = mask_profanity(text)
        if mapped and re.match(r"^[.,%:]\d|^%$|^'(s|re|ll|ve|d|t|m)\b", text, re.I) and a - mapped[-1]["end_us"] < 300_000:
            prev = mapped[-1]                                       # ASR token split ("0" + ".9", "it" + "'s"): one word
            prev.update(text=prev["text"] + text, end_us=max(b, prev["end_us"]),
                        confidence=min(prev["confidence"], w["confidence"]))
            continue
        mapped.append({"text": text, "start_us": a, "end_us": max(b, a + 80_000), "confidence": w["confidence"],
                       "stress": bool(EXCLAIM.search(w["text"]))})
    cues, cur = [], []

    def flush():
        if cur:
            cues.append({"start_us": cur[0]["start_us"], "end_us": cur[-1]["end_us"],
                         "text": " ".join(x["text"] for x in cur), "words": list(cur),
                         "min_confidence": min(x["confidence"] for x in cur)})
            cur.clear()
    weak_end = {"the", "a", "an", "to", "of", "and", "or", "but", "is", "are", "my", "your", "in", "on",
                "at", "for", "with", "i", "we", "so"}
    for w in mapped:
        if cur:
            gap = w["start_us"] - cur[-1]["end_us"]
            last = re.sub(r"[^a-z']", "", cur[-1]["text"].lower())
            full = len(cur) >= max_w and not (last in weak_end and len(cur) < max_w + 2)   # don't end on "the"
            starter = re.sub(r"[^a-z']", "", w["text"].lower()) in {"what", "how", "why", "oh", "wait", "look", "okay", "ok", "yes", "no"}
            if full or w["end_us"] - cur[0]["start_us"] > max_us or gap > 700_000 or (gap >= 250_000 and len(cur) >= 2) \
                    or (starter and len(cur) >= 2 and last not in weak_end and last not in ("no", "oh")):
                flush()
        cur.append(w)
        if PUNCT_END.search(w["text"]):
            flush()
    flush()
    # merge a too-fast cue with its neighbour when they run together and still fit on screen
    merged: list[dict] = []
    for c in cues:
        if merged:
            prev = merged[-1]
            fast = len(prev["text"]) / max((c["start_us"] - prev["start_us"]) / 1e6, 0.05) > scfg.get("max_cps", 22)
            if fast and c["start_us"] - prev["end_us"] < 300_000 and len(prev["text"]) + len(c["text"]) + 1 <= scfg.get("max_cue_chars", 34):
                prev.update(end_us=c["end_us"], text=prev["text"] + " " + c["text"], words=prev["words"] + c["words"],
                            min_confidence=min(prev["min_confidence"], c["min_confidence"]))
                continue
        merged.append(c)
    cues = merged
    _rebalance_runs(cues, int(scfg.get("rebalance_max_shift_s", 0.35) * 1e6))
    min_show = int(scfg.get("min_cue_s", 0.6) * 1e6)
    for i, a in enumerate(cues):
        nxt = cues[i + 1]["start_us"] if i + 1 < len(cues) else a["end_us"] + 1_000_000
        want = max(a["end_us"], a["start_us"] + min_show, a["start_us"] + int(len(a["text"]) / scfg.get("target_cps", 17) * 1e6))
        a["end_us"] = min(want, nxt)                 # extend into the gap, never overlap the next cue
        if 0 < nxt - a["end_us"] < 250_000:
            a["end_us"] = nxt
    return cues


def _rebalance_runs(cues: list[dict], max_shift: int) -> None:
    """Within back-to-back cues, share display time by text length (even reading speed),
    moving each boundary at most max_shift from where the words actually fall."""
    i = 0
    while i < len(cues):
        j = i
        while j + 1 < len(cues) and cues[j + 1]["start_us"] - cues[j]["end_us"] < 120_000:
            j += 1
        if j > i:
            run = cues[i:j + 1]
            a, b = run[0]["start_us"], run[-1]["end_us"]
            weights = [len(c["text"]) + 3 for c in run]
            tot = sum(weights)
            t = a
            for k, c in enumerate(run[:-1]):
                t += int((b - a) * weights[k] / tot)
                actual = run[k + 1]["start_us"]
                boundary = max(actual - max_shift, min(actual + max_shift, t))
                boundary = max(boundary, c["start_us"] + 200_000)
                c["end_us"] = boundary
                run[k + 1]["start_us"] = boundary
        i = j + 1


# ----------------------------------------------------------------------------- motion and sound
def zoom_events(style: dict, cand: dict, words: list[dict], fmap, out_dur: int, cfg: dict) -> list[dict]:
    z = style["zoom"]
    if z["max_per_10s"] <= 0 or z["anchor"] == "none":
        return []
    sig = cand.get("signals", {})
    anchors: list[tuple[int, float, str]] = []
    if z["anchor"] in ("impact", "speech_stress") and sig.get("payoff_us"):
        t = fmap(sig["payoff_us"])
        if t is not None:
            anchors.append((t, 1.0, "payoff"))
    if z["anchor"] == "speech_stress":
        sent: list[dict] = []
        for w in words + [None]:
            if w is not None:
                sent.append(w)
            if sent and (w is None or re.search(r"[.!?]$", w["text"])):
                text = " ".join(x["text"] for x in sent)
                if EXCLAIM.search(text):
                    t = fmap(sent[0]["start_us"])
                    if t is not None:
                        anchors.append((t, 0.7, f"stressed line '{text[:30]}'"))
                sent = []
    if z["anchor"] == "center_push":
        t = fmap(sig.get("payoff_us") or cand["boundaries"]["start_us"]) or 0
        anchors.append((max(0, t - int(z["ease_in_s"] * 1e6)), 0.5, "slow push into the payoff"))
    limit = max(1, int(out_dur / 10e6 * z["max_per_10s"] + 0.5))
    gap = int(cfg["edit"]["zoom_min_gap_s"] * 1e6)
    chosen: list[dict] = []
    for t, strength, why in sorted(anchors, key=lambda a: -a[1]):
        if len(chosen) >= limit:
            break
        if any(abs(t - c["anchor_us"]) < gap for c in chosen):
            continue
        lo, hi = z["scale"]
        scale = round(lo + (hi - lo) * strength, 3)
        ein, hold, eout = (int(z[k] * 1e6) for k in ("ease_in_s", "hold_s", "ease_out_s"))
        start = max(0, t - ein)
        chosen.append({"anchor_us": t, "start_us": start, "full_us": start + ein, "release_us": start + ein + hold,
                       "end_us": min(out_dur, start + ein + hold + eout), "scale": scale, "why": why})
    return sorted(chosen, key=lambda c: c["start_us"])


def sfx_events(style: dict, cand: dict, words_out: list[dict], zooms: list[dict], segs: list[dict],
               fmap, out_dur: int, cfg: dict) -> tuple[list[dict], list[str]]:
    sx = style["sfx"]
    allowed = set(sx["allowed"])
    if not allowed or sx["max_per_10s"] <= 0:
        return [], []
    guard = int(cfg["edit"]["sfx_speech_guard_s"] * 1e6)
    sig = cand.get("signals", {})
    wanted: list[tuple[int, str, str, int]] = []      # (out_us, asset, why, duration_us)
    p = fmap(sig["payoff_us"]) if sig.get("payoff_us") else None
    if p is not None and sig.get("impact_score", 0) >= 0.15:
        if "impact" in allowed:
            wanted.append((p, "impact", "reinforce the on-screen impact", 600_000))
        if "riser" in allowed:
            wanted.append((max(0, p - 1_200_000), "riser", "build tension into the payoff", 1_200_000))
    teaser = next((s for s in segs if s["role"] == "teaser"), None)
    if teaser and "whoosh" in allowed:
        cut = int((teaser["src_end_us"] - teaser["src_start_us"]) / teaser["speed"])
        wanted.append((max(0, cut - 200_000), "whoosh", "mark the jump from teaser back to the start", 450_000))
    if "pop" in allowed:
        for z in zooms:
            wanted.append((z["full_us"], "pop", f"accent the punch-in ({z['why']})", 90_000))
    limit = max(1, int(out_dur / 10e6 * sx["max_per_10s"] + 0.5))
    events, notes, used = [], [], {}
    priority = {"impact": 0, "riser": 1, "whoosh": 2, "record_scratch": 3, "pop": 4}
    for t, asset, why, dur in sorted(wanted, key=lambda w: (priority.get(w[1], 9), w[0])):
        if any(abs(t - e["out_us"]) < 350_000 for e in events):
            notes.append(f"{asset} at {t / 1e6:.2f}s dropped: would stack on another effect")
            continue
        if len(events) >= limit:
            notes.append(f"{asset} at {t / 1e6:.2f}s dropped: style limit {sx['max_per_10s']}/10 s")
            continue
        if sx.get("never_over_speech") and asset != "impact" and _overlaps_speech(words_out, t, t + dur, guard):
            notes.append(f"{asset} at {t / 1e6:.2f}s dropped: would play over speech")
            continue
        if asset == "impact" and _overlaps_speech(words_out, t, t + 250_000, 0):
            notes.append("impact effect dropped: lands on a spoken word (never hide a line under an effect)")
            continue
        if used.get(asset, 0) >= 2:
            notes.append(f"{asset} dropped: never repeat one effect more than twice per short")
            continue
        used[asset] = used.get(asset, 0) + 1
        events.append({"asset": asset, "out_us": t, "level_db": sx["level_db"], "why": why})
    return sorted(events, key=lambda e: e["out_us"]), notes


# ----------------------------------------------------------------------------- plan
def make_plan(candidate: dict, transcript: dict, cfg: dict, *, style_sel: dict, framing: dict,
              game: str | None = None, music_covered: bool = False, flash_mitigation: dict | None = None,
              black_trim: dict | None = None) -> dict:
    st = style_sel["params"]
    b = dict(candidate["boundaries"])
    if black_trim:                                   # never open or close on black (fades in the source)
        b["start_us"] = max(b["start_us"], black_trim.get("start_us", b["start_us"]))
        b["end_us"] = min(b["end_us"], black_trim.get("end_us", b["end_us"]))
        candidate = dict(candidate, boundaries=b)
    words = _words(transcript, b["start_us"], b["end_us"])
    segs, seg_notes = build_segments(candidate, words, st, cfg)
    if black_trim and (black_trim.get("start_us") or black_trim.get("end_us")):
        seg_notes.append(f"trimmed black edges: {black_trim}")
    fmap, main_dur = out_time_map(segs)
    freeze = int(st.get("freeze_end_s", 0) * 1e6)
    out_dur = main_dur + freeze
    cues = caption_cues(words, fmap, st, cfg["render"]["subtitles"])
    for c in cues:                                   # never past the end of the clip's speech timeline
        c["end_us"] = min(c["end_us"], main_dur)
    cues = [c for c in cues if c["end_us"] - c["start_us"] >= 150_000]
    cap_style = dict(cfg["render"]["subtitles"]) | st["caption"]
    # wrap inside the safe area with room for the 18% word pop
    cap_style["margin_h"] = max(cap_style.get("margin_h", 80), cfg["qa"]["safe_area"]["side_px"] + 40)
    cp = cfg["caption_placement"]
    H = cfg["render"]["height"]
    sy = framing.get("subject_y", 0.5)
    band_top = 1 - (cap_style["margin_v"] + cap_style["size"] * 2.4) / H      # two lines of text
    band_bot = 1 - cap_style["margin_v"] / H
    placement = "bottom"
    if framing["layout"] == "tracked_crop" and band_top - cp["subject_clearance"] <= sy <= band_bot + cp["subject_clearance"]:
        cap_style["alignment"], cap_style["margin_v"] = 8, cp["alt_margin_top_px"]
        placement = f"upper band: subject sits at {sy:.0%} of the frame height, inside the default caption band"
    words_out = [w for c in cues for w in c["words"]]
    zooms = zoom_events(st, candidate, words, fmap, main_dur, cfg)
    sfx, sfx_notes = sfx_events(st, candidate, words_out, zooms, segs, fmap, main_dur, cfg)
    hook = make_hook(st["hook"]["device"], words, candidate.get("signals", {}).get("payoff_us"), game)
    if cfg["render"]["subtitles"].get("mask_profanity", True):
        hook["text"] = mask_profanity(hook["text"])
    profane = len(PROFANITY.findall(" ".join(w["text"] for w in words)))
    hook["start_us"], hook["end_us"] = 0, int(cfg["edit"]["hook_duration_s"] * 1e6) if hook["text"] else 0
    contribution = []
    if any(s["role"] == "teaser" for s in segs):
        contribution.append({"type": "editorial_restructuring", "detail": "cold-open teaser of the payoff, then the build-up",
                             "provenance": "automated"})
    if hook["device"] == "context":
        contribution.append({"type": "on_screen_context", "detail": hook["text"], "provenance": "automated; operator review required"})
    elif hook["device"] in ("quote", "tease"):
        contribution.append({"type": "narrative_framing", "detail": f"hook from the speaker's own line: {hook['text']}",
                             "provenance": "automated; operator review required"})
    effects = len(zooms) + len(sfx) + sum(1 for s in segs if s["role"] == "ramp")
    if effects >= 2:
        contribution.append({"type": "substantive_editing",
                             "detail": f"{len(zooms)} punch-ins, {len(sfx)} sound effects, "
                                       f"{sum(1 for s in segs if s['role'] == 'ramp')} speed ramp(s), framing: {framing['layout']}",
                             "provenance": "automated"})
    return {
        "plan_id": f"plan_{candidate['candidate_id'][5:]}_{style_sel['name']}_v2",
        "candidate_id": candidate["candidate_id"], "source_id": candidate["source_id"], "version": 2,
        "intent": f"Present the moment: \"{candidate['transcript_excerpt'][:80]}\"",
        "style": {k: style_sel[k] for k in ("name", "score", "selected_because", "runner_up", "runner_up_reason",
                                             "profile", "all_scores", "excluded")},
        "structure": {"name": "cold_open" if any(s["role"] == "teaser" for s in segs) else "linear_build",
                      "notes": seg_notes},
        "window": {"src_start_us": b["start_us"], "src_end_us": b["end_us"]},
        "timeline": segs,
        "framing": framing,
        "zooms": zooms,
        "sfx": sfx, "sfx_notes": sfx_notes,
        "subtitles": {"cues": cues, "style": cap_style, "placement": placement},
        "hook": hook,
        "grade": st.get("grade", {}),
        "music_covered_by_licence": music_covered,
        "brand_safety": {"profanity_count": profane, "captions_masked": bool(cfg["render"]["subtitles"].get("mask_profanity", True)),
                         "note": "audio is not bleeped; profanity in speech may still limit ad suitability" if profane else "clean"},
        "flash_mitigation": flash_mitigation,
        "black_trim": black_trim,
        "freeze_end_us": freeze,
        "audio": {"loudness_target_lufs": cfg["render"]["loudness_target_lufs"],
                  "true_peak_dbtp": cfg["render"]["true_peak_dbtp"], "music": None},
        "duration_us": out_dur,
        "signals": candidate.get("signals", {}),
        "contribution": contribution,
        "contribution_note": "automated contributions need operator review before they count for publishing",
    }


# backward-compatible helper used by older tests
def subtitle_cues(transcript: dict, start_us: int, end_us: int, scfg: dict) -> list[dict]:
    words = _words(transcript, start_us, end_us)
    style = {"caption": {"animation": "none", "case": "sentence"}}
    return caption_cues(words, lambda t, include_teaser=False: t - start_us, style, scfg)
