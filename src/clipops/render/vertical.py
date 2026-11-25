"""Render an edit plan to a finished 9:16 short (spec 9.2).

Pass A, picture and source audio in one encode:
  framing (tracked crop from sendcmd keyframes, or blur fill) → per-segment
  trim and speed → concat → zoom punch-ins (zoompan) → grade → captions and hook (libass)
  → end freeze; audio: per-segment trim + atempo → concat → silence under the freeze.
  Output is a mezzanine (video final quality, PCM audio). The source-audio stem is
  kept for QA's music screen.
Pass B, sound design and loudness: registered SFX are mixed at levels relative
  to the measured stem peak, two-pass loudnorm plus a limiter run, and the video
  is stream-copied.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import yaml

from ..editing.framing import sendcmd_crop_x
from ..media import run
from ..runreport import StageFailed
from ..storage.artefacts import sha256_file
from .subtitles import build_ass

_JSON = re.compile(r"\{[^{}]*\"input_i\"[^{}]*\}", re.S)


def _filter_path(p: Path) -> str:
    return str(p).replace("\\", "/").replace(":", r"\:").replace("'", r"\'")


def _even(x: float) -> int:
    return int(round(x / 2)) * 2


def measure_loudness(path: Path, target: float, tp: float) -> dict:
    p = run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(path), "-vn",
             "-af", f"loudnorm=I={target}:TP={tp}:LRA=11:print_format=json", "-f", "null", "-"],
            code="loudness_measure_failed")
    m = _JSON.search(p.stderr.decode(errors="replace"))
    if not m:
        raise StageFailed("loudness_parse_failed", "bug", "loudnorm JSON not found")
    return json.loads(m.group(0))


def _peak_db(path: Path) -> float:
    p = run(["ffmpeg", "-hide_banner", "-i", str(path), "-af", "volumedetect", "-f", "null", "-"], code="peak_failed")
    m = re.search(r"max_volume:\s*(-?[\d.]+) dB", p.stderr.decode(errors="replace"))
    return float(m.group(1)) if m else -20.0


def zoom_expr(zooms: list[dict]) -> str:
    if not zooms:
        return "1"
    terms = []
    for z in zooms:
        a, f, r, e = (z[k] / 1e6 for k in ("start_us", "full_us", "release_us", "end_us"))
        ein, eout = max(f - a, 0.02), max(e - r, 0.02)
        terms.append(f"{z['scale'] - 1:.4f}*max(0,min(min(1,(in_time-{a:.3f})/{ein:.3f}),min(1,({e:.3f}-in_time)/{eout:.3f})))")
    return "1+" + "+".join(terms)


def _video_base(plan: dict, src_w: int, src_h: int, cmds: Path, W: int, H: int, fps: int) -> str:
    fr = plan["framing"]
    if fr["layout"] == "tracked_crop":
        cw = _even(src_h * 9 / 16)
        x0 = max(0, min(src_w - cw, int(fr["keyframes"][0]["cx"] * src_w - cw / 2))) if fr["keyframes"] else 0
        return (f"[0:v]fps={fps},sendcmd=f='{_filter_path(cmds)}',crop@trk=w={cw}:h={_even(src_h)}:x={x0}:y=0,"
                f"scale={W}:{H}:flags=lanczos,setsar=1[base]")
    if fr["layout"] == "full":
        return f"[0:v]fps={fps},scale={W}:{H}:force_original_aspect_ratio=decrease,pad={W}:{H}:(ow-iw)/2:(oh-ih)/2,setsar=1[base]"
    return (f"[0:v]fps={fps},split[s1][s2];"
            f"[s1]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},boxblur=24:2,eq=brightness=-0.12[bg];"
            f"[s2]scale={W}:-2[fg];[bg][fg]overlay=(W-w)/2:(H-h)/2,setsar=1[base]")


def render(plan: dict, src: Path, out_dir: Path, cfg: dict, src_w: int, src_h: int) -> dict:
    r = cfg["render"]
    W, H, fps = r["width"], r["height"], r["fps"]
    repo = Path(cfg["_repo"])
    short_id = "short_" + plan["plan_id"][5:]
    out_dir.mkdir(parents=True, exist_ok=True)
    win_a = plan["window"]["src_start_us"]
    win_dur = (plan["window"]["src_end_us"] - win_a) / 1e6
    # files
    cmds = out_dir / f"{short_id}.crop.cmd"
    if plan["framing"]["layout"] == "tracked_crop":
        cmds.write_text(sendcmd_crop_x(plan["framing"]["keyframes"], src_w, _even(src_h * 9 / 16)))
    ass_path = out_dir / f"{short_id}.ass"
    ass_path.write_text(build_ass(plan["subtitles"]["cues"], W, H, plan["subtitles"]["style"], plan.get("hook")))
    segs = plan["timeline"]
    n = len(segs)
    g = plan.get("grade") or {}
    freeze = plan.get("freeze_end_us", 0) / 1e6
    # --- pass A graph
    parts = [_video_base(plan, src_w, src_h, cmds, W, H, fps)]
    parts.append(f"[base]split={n}" + "".join(f"[v{i}]" for i in range(n)) if n > 1 else "[base]null[v0]")
    parts.append("[0:a]aresample=48000," + (f"asplit={n}" + "".join(f"[a{i}]" for i in range(n)) if n > 1 else "anull[a0]"))
    for i, s in enumerate(segs):
        a, b = (s["src_start_us"] - win_a) / 1e6, (s["src_end_us"] - win_a) / 1e6
        sp = s["speed"]
        # fps after the speed change duplicates frames for slow motion (real frames, not stretched timestamps)
        parts.append(f"[v{i}]trim=start={a:.3f}:end={b:.3f},setpts=(PTS-STARTPTS)/{sp},fps={fps}[sv{i}]")
        at = f",atempo={sp}" if abs(sp - 1) > 1e-6 else ""
        parts.append(f"[a{i}]atrim=start={a:.3f}:end={b:.3f},asetpts=PTS-STARTPTS{at}[sa{i}]")
    parts.append("".join(f"[sv{i}]" for i in range(n)) + f"concat=n={n}:v=1:a=0[cat]")
    parts.append("".join(f"[sa{i}]" for i in range(n)) + f"concat=n={n}:v=0:a=1[acat]")
    vchain = "[cat]"
    if plan["zooms"]:
        vchain += (f"zoompan=z='{zoom_expr(plan['zooms'])}':x='iw/2-(iw/zoom/2)':y='(ih-ih/zoom)*0.46':"
                   f"d=1:s={W}x{H}:fps={fps},")
    fm = plan.get("flash_mitigation")
    if fm:
        vchain += f"photosensitivity=f={fm['frames']}:t={fm['threshold']},"   # WCAG 2.3.1 remedy (spec 4.9)
    vchain += f"eq=contrast={g.get('contrast', 1.0)}:saturation={g.get('saturation', 1.0)},"
    vchain += f"subtitles=filename='{_filter_path(ass_path)}':fontsdir='{_filter_path(repo / 'assets' / 'fonts')}',"
    if freeze > 0:
        vchain += f"tpad=stop_mode=clone:stop_duration={freeze:.3f},"
    vchain += f"setpts=N/({fps}*TB),format=yuv420p,setsar=1[v]"   # explicit rate: FRAME_RATE is unknown after a 24→30 fps concat
    parts.append(vchain)
    parts.append(f"[acat]apad=pad_dur={freeze:.3f}[astem]" if freeze > 0 else "[acat]anull[astem]")
    mezz = out_dir / f"{short_id}.mezz.mkv"
    run(["ffmpeg", "-hide_banner", "-v", "error", "-y", "-ss", f"{win_a / 1e6:.3f}", "-t", f"{win_dur:.3f}",
         "-i", str(src), "-filter_complex", ";".join(parts), "-map", "[v]", "-map", "[astem]",
         "-c:v", r["video_codec"], "-crf", str(r["crf"]), "-preset", r["preset"],
         "-c:a", "pcm_s16le", str(mezz)], code="render_failed", timeout=7200)
    stem = out_dir / f"{short_id}.stem.wav"
    run(["ffmpeg", "-v", "error", "-y", "-i", str(mezz), "-vn", "-c:a", "pcm_s16le", str(stem)], code="stem_failed")
    # --- pass B: SFX mix at levels relative to the stem peak, then loudness
    reg = yaml.safe_load((repo / "config" / "assets.yaml").read_text())["sfx"]
    stem_peak = _peak_db(stem)
    inputs, mix = ["-i", str(stem)], []
    used_assets = []
    for k, e in enumerate(plan["sfx"], start=1):
        asset = reg.get(e["asset"])
        if not asset:
            raise StageFailed("unregistered_asset", "policy", f"SFX '{e['asset']}' is not in config/assets.yaml (spec 4.8)")
        apath = repo / asset["path"]
        if sha256_file(apath) != asset["sha256"]:
            raise StageFailed("asset_hash_mismatch", "policy", f"{apath.name} differs from its registered hash")
        inputs += ["-i", str(apath)]
        gain = (stem_peak + e["level_db"]) - (-3.0)            # assets are normalised to -3 dBFS peak
        ms = int(e["out_us"] / 1000)
        mix.append(f"[{k}:a]aresample=48000,adelay={ms}|{ms},volume={gain:.2f}dB[x{k}]")
        used_assets.append({"asset": e["asset"], "sha256": asset["sha256"], "gain_db": round(gain, 2), "at_s": ms / 1000})
    mixed = out_dir / f"{short_id}.mix.wav"
    if mix:
        graph = ";".join(mix) + ";[0:a]" + "".join(f"[x{k}]" for k in range(1, len(mix) + 1)) + \
            f"amix=inputs={len(mix) + 1}:normalize=0:duration=first[m]"
        run(["ffmpeg", "-v", "error", "-y", *inputs, "-filter_complex", graph, "-map", "[m]",
             "-c:a", "pcm_s16le", str(mixed)], code="sfx_mix_failed")
    else:
        mixed = stem
    meas = measure_loudness(mixed, r["loudness_target_lufs"], r["true_peak_dbtp"])
    out = out_dir / f"{short_id}.mp4"
    target, ceiling = r["loudness_target_lufs"], r["true_peak_dbtp"]
    # Deterministic loudness: optional compression (high crest factor, e.g. gunfire) → gain → limiter,
    # then measure the ENCODED file and correct gain and limiter until both targets hold. FFmpeg's loudnorm
    # was dropped here: it missed targets on short, transient-dense clips (measured -19.7 vs -14 LUFS, E-046).
    plr = float(meas["input_tp"]) - float(meas["input_i"])
    comp = "acompressor=threshold=-24dB:ratio=3:attack=5:release=150:makeup=2," if plr > r.get("compress_above_plr_db", 18) else ""
    gain = target - float(meas["input_i"]) - (2.0 if comp else 0.0)
    limit_db = ceiling - 1.0
    attempts = []
    for _ in range(8):
        af = (f"aresample=48000,{comp}volume={gain:.2f}dB,"
              f"alimiter=limit={10 ** (limit_db / 20):.4f}:attack=5:release=60:level=disabled")
        run(["ffmpeg", "-v", "error", "-y", "-i", str(mezz), "-i", str(mixed), "-map", "0:v:0", "-map", "1:a:0",
             "-c:v", "copy", "-af", af, "-c:a", r["audio_codec"], "-b:a", r["audio_bitrate"],
             "-movflags", "+faststart", "-shortest", str(out)], code="final_mux_failed")
        m = measure_loudness(out, target, ceiling)
        li, tp = float(m["input_i"]), float(m["input_tp"])
        attempts.append({"gain_db": round(gain, 2), "limiter_db": round(limit_db, 2), "lufs": li, "true_peak": tp,
                         "compressed": bool(comp)})
        ok_l = abs(li - target) <= r.get("loudness_tolerance_render_lu", 0.7)
        ok_p = tp <= ceiling - 0.05
        if ok_l and ok_p:
            break
        if not ok_p:
            limit_db -= max(0.3, tp - ceiling + 0.2)
        if not ok_l:
            gain += max(-6.0, min(6.0, target - li))
            if li < target - 3 and not comp:      # limiter is eating the gain: reduce crest factor instead
                comp = "acompressor=threshold=-24dB:ratio=3:attack=5:release=150:makeup=2,"
    mezz.unlink(missing_ok=True)
    if mixed != stem:
        mixed.unlink(missing_ok=True)
    return {"short_id": short_id, "plan_id": plan["plan_id"], "path": str(out), "ass_path": str(ass_path),
            "stem_path": str(stem), "expected_duration_us": plan["duration_us"], "loudness_first_pass": meas,
            "encoder": r["video_codec"], "layout": plan["framing"]["layout"], "sfx_used": used_assets,
            "true_peak_attempts": attempts, "loudness_attempts": attempts,
            "style": plan["style"]["name"]}
