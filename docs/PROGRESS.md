# Progress Ledger

Append-only. CHECKPOINT entries are safe resumption points.

---

## 2026-11-21: Phase 0 orientation  [ARCH, MEDIA, SEC, WRITER, RIGHTS]
- Created the repo layout at the repo root (ADR-0001). Copied the spec to
  `docs/MASTER_PROMPT.docx` (sha256 97d729a0…af68) and converted it with pandoc
  3.1.3 to `docs/MASTER_PROMPT.md`. Verified: 18 chapters and appendices A-K
  are present (smoke test).
- Wrote `scripts/inspect_hardware.py` (stdlib, portable) and ran it in the dev
  container: CPU-only, 4 vCPU, 15.7 GiB, libx264 ~54 fps at 1080p30; all listed
  hardware encoders fail with a recorded root cause; no libvmaf. Report labelled
  `cloud-dev-container`.
- Wrote `scripts/check_credentials.py`: all platform credentials absent.
- Created the five ledgers, AMENDMENTS (24 items, VERIFY register), KNOWLEDGE_MAP,
  DISCOVERY, BLOCKERS (B-01-B-07), OPERATOR_TODO (Q1-Q9), ROADMAP, CLAUDE.md, README.
- Initial platform research (SECONDARY): YouTube docs self-contradict on
  upload quota cost and the private restriction. TikTok unaudited clients are
  private-only. IG publish limit conflicts (50 vs 100). Twitch download endpoint
  is scope-gated. Rockstar policy is non-commercial only.
- Package `clipops` with `clipops health`, smoke tests, and a GitHub Actions CI skeleton.

### CHECKPOINT 2026-11-21-a
- **Phase:** 0. **Next gate:** G0, blocked only by B-01 (operator machine inspection).
- **Verified:** `pytest -m smoke` passes; `clipops health` exits 0 (with the
  operator-machine warning); hardware script produces JSON and MD.
- **Half-finished:** none.
- **Exact next step:** P0-12 walking skeleton. Generate a licence-free synthetic
  fixture with FFmpeg (testsrc2 plus synthetic or TTS-free speech-like audio; or
  a short self-recorded voice clip if the operator supplies one), then
  ffprobe ingest → transcription (install faster-whisper tiny/base, CPU int8;
  check the model licence first) → one candidate → 1080×1920 render with burned
  ASS captions → checks: duration, integrated loudness, blackdetect/silencedetect.
  In parallel: P1-01 full read of platform docs.
- **Relevant files:** docs/ROADMAP.md, docs/BLOCKERS.md, docs/AMENDMENTS.md,
  config/settings.example.yaml.
- **Hazards:** the container is ephemeral (push every increment). Platform
  evidence is SECONDARY, so do not build adapters on it. The GTA focus is an
  assumption (A-001).
