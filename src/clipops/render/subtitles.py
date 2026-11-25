"""ASS subtitle generation with style-driven animation (libass renders it in FFmpeg).

Animations:
- pop_word: the whole cue is visible; the word being spoken pops (scale ease)
  and stressed words take the emphasis colour;
- karaoke: words fill with the emphasis colour as they are spoken (\\kf);
- fade: gentle fade in and out;
- none: static.
A separate "Hook" style draws the hook or context banner in the top safe band.
"""
from __future__ import annotations


def _ts(us: int) -> str:
    cs = max(0, round(us / 10_000))
    h, rem = divmod(cs, 360_000)
    m, rem = divmod(rem, 6_000)
    s, cs = divmod(rem, 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def _escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("{", "(").replace("}", ")").replace("\n", " ")


def _font(name: str) -> tuple[str, int]:
    return (name[:-5].strip(), -1) if name.endswith(" Bold") else (name, 0)


def _cue_lines(c: dict, s: dict) -> list[str]:
    anim = s.get("animation", "none")
    emph = s.get("emphasis") or "&H0000E5FF"
    words = c.get("words") or []
    if anim == "pop_word" and words:
        out = []
        for i, w in enumerate(words):
            a = w["start_us"]
            b = words[i + 1]["start_us"] if i + 1 < len(words) else c["end_us"]
            if b <= a:
                continue
            parts = []
            for j, x in enumerate(words):
                t = _escape(x["text"])
                if j == i:
                    col = f"\\c{emph}" if x.get("stress") else ""
                    parts.append("{" + col + "\\fscx100\\fscy100\\t(0,70,\\fscx118\\fscy118)\\t(70,170,\\fscx106\\fscy106)}"
                                 + t + "{\\r}")
                elif x.get("stress") and j < i:
                    parts.append("{\\c" + emph + "}" + t + "{\\r}")
                else:
                    parts.append(t)
            out.append(f"Dialogue: 0,{_ts(a)},{_ts(b)},Cap,,0,0,0,,{' '.join(parts)}")
        return out
    if anim == "karaoke" and words:
        parts, prev = [], c["start_us"]
        for w in words:
            gap = max(0, (w["start_us"] - prev) // 10_000)
            dur = max(1, (w["end_us"] - w["start_us"]) // 10_000)
            parts.append((f"{{\\k{gap}}}" if gap else "") + f"{{\\kf{dur}}}" + _escape(w["text"]))
            prev = w["end_us"]
        return [f"Dialogue: 0,{_ts(c['start_us'])},{_ts(c['end_us'])},Cap,,0,0,0,,{' '.join(parts)}"]
    if anim == "fade":
        return [f"Dialogue: 0,{_ts(c['start_us'])},{_ts(c['end_us'])},Cap,,0,0,0,,{{\\fad(120,120)}}{_escape(c['text'])}"]
    return [f"Dialogue: 0,{_ts(c['start_us'])},{_ts(c['end_us'])},Cap,,0,0,0,,{_escape(c['text'])}"]


def build_ass(cues: list[dict], width: int, height: int, s: dict, hook: dict | None = None) -> str:
    fam, bold = _font(s.get("font", "DejaVu Sans"))
    anim = s.get("animation", "none")
    emph = s.get("emphasis") or "&H0000E5FF"
    primary, secondary = ("&H00FFFFFF", "&H000000FF") if anim != "karaoke" else (emph, "&H00FFFFFF")
    hook_margin = s.get("hook_margin_v", 300)
    head = [
        "[Script Info]", "ScriptType: v4.00+", f"PlayResX: {width}", f"PlayResY: {height}",
        "WrapStyle: 0", "ScaledBorderAndShadow: yes", "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, "
        "Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, "
        "Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        f"Style: Cap,{fam},{s.get('size', s.get('font_size', 64))},{primary},{secondary},&H00000000,&H64000000,"
        f"{bold},0,0,0,100,100,0,0,1,{s.get('outline', 4)},1,{s.get('alignment', 2)},{s.get('margin_h', 80)},{s.get('margin_h', 80)},"
        f"{s.get('margin_v', 420)},1",
        f"Style: Hook,{fam},72,&H00FFFFFF,&H000000FF,&H00000000,&HA0000000,"
        f"-1,0,0,0,100,100,0,0,3,14,0,8,90,90,{hook_margin},1",
        "", "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    ev: list[str] = []
    if hook and hook.get("text"):
        ev.append(f"Dialogue: 1,{_ts(hook['start_us'])},{_ts(hook['end_us'])},Hook,,0,0,0,,"
                  f"{{\\fad(150,200)}}{_escape(hook['text'])}")
    for c in cues:
        ev += _cue_lines(c, s)
    return "\n".join(head + ev) + "\n"
