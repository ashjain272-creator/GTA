"""Audio event tagging with YAMNet (AudioSet, 521 classes): music screen (R26)
and event signals (explosions, gunshots, laughter, screams) for candidates.

Model: YAMNet TFLite, Apache-2.0 (E-036). Loaded through LiteRT on CPU.
The file is fetched from the URL in config and verified against a pinned
sha256 before use. There is no silent fallback: if the model or runtime is
missing, the stage fails, and downstream gates treat the source as unscreened
(fail closed).
"""
from __future__ import annotations

import hashlib
import json
import urllib.request
from pathlib import Path

import numpy as np

from ..media import decode_audio_f32
from ..runreport import StageFailed

SR = 16000
WINDOW = 15600                      # 0.975 s, the model's native input
EVENT_CLASSES = {
    "music": ["Music"],
    "speech": ["Speech"],
    "laughter": ["Laughter", "Giggle", "Chuckle, chortle", "Belly laugh"],
    "scream": ["Screaming", "Shout", "Yell"],
    "explosion": ["Explosion", "Burst, pop", "Boom"],
    "gunshot": ["Gunshot, gunfire", "Machine gun", "Fusillade"],
    "vehicle": ["Vehicle", "Car", "Engine", "Skidding", "Tire squeal"],
    "crash": ["Smash, crash", "Bang"],
}


def _fetch(url: str, dest: Path, sha256: str) -> Path:
    if not dest.is_file():
        dest.parent.mkdir(parents=True, exist_ok=True)
        tmp = dest.with_suffix(dest.suffix + ".part")
        try:
            urllib.request.urlretrieve(url, tmp)
        except Exception as e:  # noqa: BLE001
            raise StageFailed("model_download_failed", "transient", f"{url}: {e}") from e
        tmp.replace(dest)
    digest = hashlib.sha256(dest.read_bytes()).hexdigest()
    if digest != sha256:
        raise StageFailed("model_hash_mismatch", "config",
                          f"{dest.name}: sha256 {digest[:12]}... != pinned {sha256[:12]}...")
    return dest


def load_model(cfg: dict):
    m = cfg["models"]["yamnet"]
    root = Path(cfg["_repo"]) / m["dir"]
    model = _fetch(m["model_url"], root / Path(m["model_url"]).name, m["model_sha256"])
    labels_p = _fetch(m["labels_url"], root / Path(m["labels_url"]).name, m["labels_sha256"])
    try:
        from ai_edge_litert.interpreter import Interpreter
    except ImportError as e:
        raise StageFailed("litert_missing", "config", "ai-edge-litert not installed: uv sync --extra asr") from e
    it = Interpreter(model_path=str(model))
    labels = json.loads(labels_p.read_text())
    return it, [labels[str(i)] for i in range(len(labels))]


def tag(path: Path, cfg: dict, hop_s: float = 0.4875) -> dict:
    it, labels = load_model(cfg)
    inp, out = it.get_input_details()[0], it.get_output_details()[0]
    it.resize_tensor_input(inp["index"], [WINDOW])
    it.allocate_tensors()
    audio = decode_audio_f32(path, sr=SR)
    if len(audio) < WINDOW:
        audio = np.pad(audio, (0, WINDOW - len(audio)))
    idx = {name: [labels.index(c) for c in classes if c in labels] for name, classes in EVENT_CLASSES.items()}
    hop = int(hop_s * SR)
    frames = []
    for start in range(0, len(audio) - WINDOW + 1, hop):
        it.set_tensor(inp["index"], audio[start:start + WINDOW])
        it.invoke()
        s = it.get_tensor(out["index"])[0]
        frames.append({"t_us": int((start + WINDOW / 2) / SR * 1e6),
                       **{k: round(float(max(s[i] for i in v)), 4) for k, v in idx.items() if v}})
    return {"model": "yamnet-tflite", "model_sha256": cfg["models"]["yamnet"]["model_sha256"],
            "window_s": WINDOW / SR, "hop_s": hop_s, "frames": frames}


def music_fraction(events: dict, start_us: int, end_us: int, threshold: float) -> float:
    fr = [f for f in events.get("frames", []) if start_us <= f["t_us"] <= end_us]
    if not fr:
        return 0.0
    return sum(1 for f in fr if f.get("music", 0.0) >= threshold) / len(fr)
