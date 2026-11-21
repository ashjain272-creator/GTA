"""ASS subtitle file generation (libass renders it inside FFmpeg)."""
from __future__ import annotations


def _ts(us: int) -> str:
    cs = max(0, round(us / 10_000))
    h, rem = divmod(cs, 360_000)
    m, rem = divmod(rem, 6_000)
    s, cs = divmod(rem, 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def _escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("{", "(").replace("}", ")").replace("\n", " ")


def build_ass(cues: list[dict], width: int, height: int, s: dict) -> str:
    head = [
        "[Script Info]", "ScriptType: v4.00+", f"PlayResX: {width}", f"PlayResY: {height}",
        "WrapStyle: 0", "ScaledBorderAndShadow: yes", "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, "
        "Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, "
        "Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        f"Style: Default,{s['font']},{s['font_size']},&H00FFFFFF,&H000000FF,&H00000000,&H64000000,"
        f"-1,0,0,0,100,100,0,0,1,{s['outline']},1,2,{s['margin_h']},{s['margin_h']},{s['margin_v']},1",
        "", "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    ev = [f"Dialogue: 0,{_ts(c['start_us'])},{_ts(c['end_us'])},Default,,0,0,0,,{_escape(c['text'])}"
          for c in cues]
    return "\n".join(head + ev) + "\n"
