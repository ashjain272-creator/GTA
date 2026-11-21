"""Stage 3 (spec 6.4): transcription with word timestamps.

Engine: faster-whisper (MIT; model weights are OpenAI Whisper conversions, MIT).
No silent fallback: if the engine is unavailable the stage fails.
"""
from __future__ import annotations

import time
from pathlib import Path

from ..media import decode_audio_f32
from ..runreport import StageFailed

SR = 16000


def transcribe(path: Path, cfg: dict) -> dict:
    acfg = cfg["asr"]
    if acfg["engine"] != "faster-whisper":
        raise StageFailed("asr_engine_unknown", "config", f"engine {acfg['engine']!r} not implemented")
    try:
        from faster_whisper import WhisperModel
    except ImportError as e:
        raise StageFailed("asr_missing", "config",
                          "faster-whisper not installed: pip install -e '.[asr]'") from e
    audio = decode_audio_f32(path, sr=SR)
    t0 = time.perf_counter()
    model = WhisperModel(acfg["model"], device=acfg["device"], compute_type=acfg["compute_type"])
    load_s = time.perf_counter() - t0
    t0 = time.perf_counter()
    segs, info = model.transcribe(audio, word_timestamps=True, vad_filter=acfg["vad_filter"],
                                  language=acfg.get("language"))
    segments = []
    for s in segs:
        words = [{"text": w.word.strip(), "start_us": int(w.start * 1e6), "end_us": int(w.end * 1e6),
                  "confidence": round(float(w.probability), 4)} for w in (s.words or [])]
        segments.append({"start_us": int(s.start * 1e6), "end_us": int(s.end * 1e6),
                         "text": s.text.strip(), "avg_logprob": round(float(s.avg_logprob), 4),
                         "no_speech_prob": round(float(s.no_speech_prob), 4), "words": words})
    run_s = time.perf_counter() - t0
    return {
        "engine": "faster-whisper", "model": acfg["model"], "compute_type": acfg["compute_type"],
        "language": info.language, "language_probability": round(float(info.language_probability), 4),
        "audio_duration_s": round(len(audio) / SR, 3),
        "timing": {"model_load_s": round(load_s, 2), "transcribe_s": round(run_s, 2),
                   "realtime_factor": round(run_s / max(len(audio) / SR, 1e-6), 3)},
        "segments": segments,
        "low_confidence_words": sum(1 for s in segments for w in s["words"] if w["confidence"] < 0.5),
    }
