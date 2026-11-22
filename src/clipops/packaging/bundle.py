"""L0 ready-to-post bundles (spec 11.4, 11.6 L0, 9.6 export profiles).

A bundle is a folder per platform with the platform-specific video, a cover
frame, draft text, required flags and posting steps. Text drafts are generated
deterministically from the transcript and are always marked as drafts for the
operator to edit. No claim is made that a title performs well (spec 18.2 S2).
The publish-gate verdict is written into the bundle. A bundle that is not
ready says so on its first line.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import yaml

from ..media import run
from ..publish.gate import evaluate
from ..storage.artefacts import sha256_file, write_json

STEPS = {
    "youtube": ["Open YouTube Studio → Create → Upload videos.", "Select video.mp4 (vertical, ≤ 60 s → classified as a Short).",
                "Paste the title and description from text.md.", "Audience: 'No, it's not made for kids'.",
                "Set visibility to Private first, review on a phone, then publish."],
    "tiktok": ["In the TikTok app: + → Upload → select video.mp4.", "Paste the caption from text.md.",
               "Choose visibility yourself (TikTok requires a manual choice).",
               "Set commercial-content disclosure if the post promotes anything.", "Post."],
    "instagram": ["In Instagram: + → Reel → select video.mp4.", "Paste the caption from text.md.",
                  "Choose cover.jpg as the cover.", "Share."],
}


def load_profile(repo: Path, platform: str) -> dict:
    return yaml.safe_load((repo / "config" / "platforms" / f"{platform}.yaml").read_text())


def draft_text(plan: dict, rights: dict, profile: dict) -> dict:
    words = plan["intent"].split('"')[1] if '"' in plan["intent"] else plan["intent"]
    first = re.split(r"(?<=[.!?])\s", words.strip())[0].strip()
    title = first[: profile["packaging"]["title_max_chars"]].rstrip() if profile["packaging"]["title_max_chars"] else ""
    lines = [first]
    grant = rights.get("grant") or {}
    if grant.get("attribution"):
        lines.append(f"Credit: {grant['attribution']}")
    for g in rights.get("game_policies", []):
        lines.append(f"Game: {g['game']}")
    tags = profile["packaging"].get("hashtags") or []
    desc = "\n".join(lines + ([" ".join(tags)] if tags else []))
    return {"title": title, "description": desc[: profile["packaging"]["description_max_chars"]],
            "status": "DRAFT: generated from the transcript; edit before posting"}


def export_video(src: Path, out: Path, profile: dict) -> None:
    e = profile["export"]
    cmd = ["ffmpeg", "-v", "error", "-y", "-i", str(src), "-map", "0:v:0", "-map", "0:a:0", "-c:v", "copy"]
    if e["audio_bitrate"] != "192k":           # renders are 192k AAC; re-encode audio only when the profile differs
        cmd += ["-c:a", "aac", "-b:a", e["audio_bitrate"], "-ar", "48000"]
    else:
        cmd += ["-c:a", "copy"]
    if not e.get("use_editlist", True):
        cmd += ["-use_editlist", "0"]
    cmd += ["-movflags", "+faststart", str(out)]
    run(cmd, code="export_failed")


def cover_frame(src: Path, out: Path, t_s: float) -> None:
    run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t_s:.3f}", "-i", str(src), "-frames:v", "1",
         "-q:v", "2", str(out)], code="cover_failed")


def make_bundle(cfg: dict, src_dir: Path, plan: dict, render_info: dict, qa: dict, platform: str,
                out_root: Path) -> dict:
    repo = Path(cfg["_repo"])
    profile = load_profile(repo, platform)
    rights = json.loads((src_dir / "rights.json").read_text())
    verdict = evaluate(cfg, src_dir, plan, render_info, qa, platform, profile)
    d = out_root / render_info["short_id"] / platform
    d.mkdir(parents=True, exist_ok=True)
    video = d / "video.mp4"
    export_video(Path(render_info["path"]), video, profile)
    cover = d / "cover.jpg"
    cover_frame(video, cover, min(1.0, plan["duration_us"] / 2e6))
    text = draft_text(plan, rights, profile)
    flags = dict(profile["packaging"].get("required_flags") or {})
    if rights.get("monetisation_allowed") != "yes":
        flags["monetisation"] = f"do not monetise (rights record: {rights.get('monetisation_allowed')})"
    header = ("READY FOR MANUAL POSTING" if verdict["ready"]
              else "NOT READY: do not post. Blocking: " + ", ".join(verdict["blocking"]))
    md = [f"# {header}", "", f"Platform: {platform} · Short: {render_info['short_id']} · Autonomy: {verdict['autonomy_level']}", "",
          "## Title (draft)", text["title"] or "(platform has no title field)", "", "## Description / caption (draft)",
          text["description"], "", f"_{text['status']}_", "", "## Required settings"]
    md += [f"- {k}: {v}" for k, v in flags.items()]
    md += ["", "## Posting steps"] + [f"{i}. {s}" for i, s in enumerate(STEPS[platform], 1)]
    md += ["", "## Gate checks"] + [f"- [{'x' if c['passed'] else ' '}] {c['name']}: {c['reason']}" for c in verdict["checks"]]
    (d / "text.md").write_text("\n".join(md) + "\n")
    meta = {"short_id": render_info["short_id"], "platform": platform, "ready": verdict["ready"],
            "verdict": verdict, "text": text, "flags": flags,
            "files": {"video": {"path": "video.mp4", "sha256": sha256_file(video)},
                      "cover": {"path": "cover.jpg", "sha256": sha256_file(cover)}},
            "export_profile": profile["export"], "watermark_allowed": profile["packaging"]["watermark_allowed"]}
    write_json(d / "bundle.json", meta)
    return meta
