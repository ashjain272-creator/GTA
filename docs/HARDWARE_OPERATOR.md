# Operator Machine: What Is Known (spec 5.3)

The full `inspect_hardware.py` output from this machine has not reached the
repository (copy and paste failed twice). This page records what is known and
where each fact comes from. When `config/hardware.json` with role
`operator-machine` is committed, it supersedes this page.

| Fact | Value | Source | Status |
|---|---|---|---|
| Machine | Mac mini | terminal prompt `ashish@Mac-mini` | MEASURED (screenshot) |
| Chip | Apple M4 | operator, About This Mac, 2026-11-24 | SECONDARY (operator-declared) |
| CPU cores | 10 logical (M4: 4 performance + 6 efficiency) | inspection script (E-040); core split from Apple's M4 specification, not read here | MEASURED / ASSUMPTION |
| Memory | 16 GB unified | operator, 2026-11-24 | SECONDARY (operator-declared) |
| GPU / ML | M4 integrated GPU (Metal), Neural Engine | implied by chip | ASSUMPTION |
| Free disk | 6.7 GB | macOS notification | MEASURED (screenshot) |
| FFmpeg | 9.0.2 (Homebrew) | install log | MEASURED (screenshot) |
| Hardware encoders | h264/hevc_videotoolbox expected; encode test results not seen | — | PENDING |
| Python | 3.12.16 via uv (system 3.9.6 too old) | install log | MEASURED (screenshot) |
| Node / git | 24.14.1 / 2.54.0 | inspection script | MEASURED |

## Decisions this enables (provisional, ADR-0012)
- Speech recognition: 16 GB unified memory fits Whisper up to medium-size
  models. Benchmark on this Mac: faster-whisper (CPU int8, current default),
  whisper.cpp with Metal, MLX Whisper. Choose by WER on gaming audio and
  realtime factor.
- Rendering: VideoToolbox (hardware) is a candidate for draft renders.
  Finals stay libx264 until a quality comparison shows VideoToolbox matches
  at the target bitrate.
- Concurrency: at most 2 heavy jobs at once (ASR and render share 16 GB).
- Storage: **blocking**. 6.7 GB free cannot hold real footage plus
  intermediates. An external SSD for `data/`, or freeing tens of GB, is
  required before real runs (B-08).
