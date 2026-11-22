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

---

## 2026-11-21: Walking skeleton (P0-12)  [ARCH, ML, MEDIA, QA, SEC]
- Network: the default environment blocked Hugging Face. With operator approval,
  created environment "GTA" adding only HF hosts (ADR-0008).
- ASR: pocketsphinx was unusable (E-018). faster-whisper base.en int8 adopted
  for the skeleton (ADR-0006).
- Implemented `clipops` stages: rights gate (fails closed; Rockstar registry
  → monetisation off), probe, transcription, loudness curve, scene cuts,
  candidates (heuristic, gated, with recorded rejections), plan (one honest
  skeleton style), 9:16 render (blur fill, libass captions, two-pass loudnorm
  plus limiter), 12 objective QA checks (blocking vs review severity),
  contact sheet, run report, resumable per-stage artefacts (ADR-0007).
- CLI: `source add`, `ingest run`, `analyse run`, `candidates generate`,
  `plan make`, `render run`, `qa run`, `demo run`, `health`.
- Defects found by running the skeleton and fixed: segment-based grouping
  merged across silences (E-014); stale cache after a logic change (R32); dead
  air inside a candidate (new gate); true peak above the ceiling (E-015);
  ranker limitation warning missing on cached runs.
- Demo (synthetic fixture): WER 0.0 on 41 words; top candidate 1.02-16.98 s vs
  planted 2-17 s; QA passed all blocking checks; one review flag (low-confidence
  "Okay,"). Recorded in reports/demo/20261121T215543Z.
- Tests: 31 pass (smoke, rights, candidates/subtitles, artefacts, resume,
  e2e including an injected-crash recovery test). CI gains an e2e job; it has
  not run on GitHub yet.

### Self-critique (spec 2.6 step 7)
1. The fixture is easy (clean TTS, synthetic video). The skeleton proves
   wiring, not quality. Every quality number here is non-transferable.
2. The ranker is a hand-weighted heuristic with no evaluation. It ranked a
   low-energy filler window (0.61) close to the real moment (0.67), so it barely
   discriminates.
3. The QA safe-area check reads configuration, not rendered pixels. Captions
   could still overflow on long words or large fonts without failing QA.

### CHECKPOINT 2026-11-21-b
- **Phase:** 0 (P0-12 done). **Next gate:** G0, blocked only by B-01.
- **Verified:** `pytest -q`: 31 passed. `clipops demo run` exits 0.
- **Half-finished:** none.
- **Exact next step:** P1-01, a full read of the platform docs (YouTube quota and
  audit, TikTok Content Posting, Instagram publishing, Twitch ToS and Developer
  Agreement) to promote E-001-E-006 and write docs/PLATFORM_LIMITS.md. Then
  P0-13 (class E URL path) and P0-15 (lockfile).
- **Relevant files:** src/clipops/orchestrator/pipeline.py (STAGE_VERSIONS:
  bump on any output-changing edit), config/settings.example.yaml,
  docs/ROADMAP.md.
- **Hazards:** HF model downloads need the "GTA" environment. Sessions on the
  Default environment will fail ASR.

---

## 2026-11-22: Platform verification (P1-01), class E path, lockfile  [RESEARCH, GROWTH, SEC, ARCH]
- With operator approval, the "GTA" environment gained six documentation hosts
  (ADR-0008 scope extended). Read at source: YouTube Data API quota, insert,
  audit and revision history; TikTok getting-started, sharing guidelines,
  upload, media transfer and scopes; Instagram content publishing and limits;
  Twitch clips reference.
- Results (E-020-E-028, docs/PLATFORM_LIMITS.md):
  - YouTube: 100 uploads/day at 1 unit each in a separate bucket; no audit
    needed; unverified projects **no longer** forced private (2026-11-02), so
    uploads default to public. New risk R33, rule: always send privacyStatus.
    Paid-placement flag no longer defaults (2026-11-16).
  - TikTok: Direct Post intended-use rules exclude own-account tools (E-024),
    so the plan is inbox/draft upload (`video.upload`). Watermarks and logos
    are forbidden on shared content (E-025).
  - Instagram: local-file resumable upload with Facebook Login for Business
    (AM-08 resolved); limit 100/24 h on the newer page vs 50 on a 2024 page.
  - Twitch: clip download only for the broadcaster and their editors.
- ADR-0009 sets the publishing route per platform. AM-25, AM-26 added.
- Still unread: Twitch ToS (legal.twitch.com not allowed), Rockstar policy
  (empty reply), YouTube Shorts criteria, IG Reels specs (E-029).
- P0-13: `clipops source classify <url>` classifies without any network
  access and drafts a permission request (spec 4.15 test 1).
- P0-15: uv.lock. CI now installs from the lockfile. 41 tests pass in the
  locked environment.

### CHECKPOINT 2026-11-22-a
- **Phase:** 0/1 overlap. G0 still blocked only by B-01. P1-01 mostly done.
- **Verified:** `.venv/bin/pytest -q`: 41 passed (locked env). Smoke passes.
- **Half-finished:** P1-01 pending items above.
- **Exact next step:** P1-02 reused-content policy wording (YouTube Help,
  TikTok and Instagram community guidelines: hosts not yet allowed), or,
  without network, P1-04 licence matrix from installed package metadata, plus
  P0-16 (measure rendered caption bounds). The YouTube adapter (Phase 7) can be
  designed now against PLATFORM_LIMITS, but must not be built as a stub.
- **Hazards:** YouTube's public default (R33). The fetch tool has its own host
  allowlist, separate from the environment, so use curl for docs.
