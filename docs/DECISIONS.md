# Decision Log (ADR format)

Append-only. A decision is superseded by a later ADR, never edited in place
beyond status changes. Revisiting requires new evidence or a changed condition.

Role tags: [ARCH] systems architect, [MEDIA] media engineer, [SEC] security,
[RIGHTS] business/rights analyst, [QA], [WRITER].

---

## ADR-0001 Repository root is the project root  [ARCH]
- **Date:** 2026-11-21 · **Status:** Accepted
- **Question:** Spec 2.4 shows the layout under a `clipops/` directory. The
  operator's Git repository (`GTA`) is empty. Nest the layout or use the repo root?
- **Options:** (a) `GTA/clipops/...`; (b) layout at repo root, Python package
  named `clipops` under `src/clipops/`.
- **Choice:** (b). The repo is the project; nesting adds a path segment to every
  command and CI step with no separation benefit.
- **Consequences:** Paths in docs are repo-relative (`docs/`, `src/clipops/`).
  Recorded as amendment AM-01.
- **Revisit if:** the repo comes to hold more than one project.

## ADR-0002 Development host is not the production host  [ARCH]
- **Date:** 2026-11-21 · **Status:** Accepted
- **Context:** This session runs in an ephemeral cloud container (4 vCPU Xeon,
  15.7 GiB RAM, no GPU, no working hardware encoder; see HARDWARE_REPORT.md,
  role `cloud-dev-container`). No operator computer is attached (checked:
  zero shared folders available).
- **Choice:** Treat the container as a dev/CI host only. Every hardware-dependent
  decision in spec 5.6 (#4, #5, #7, #9, #12 and concurrency) is **deferred**
  until `scripts/inspect_hardware.py --role operator-machine` output exists.
  Hardware-independent work proceeds.
- **Consequences:** Gate G0 cannot be fully passed (hardware report must
  describe the real machine). Blocker B-01. Code must be portable
  (Linux/macOS/Windows) because the operator's OS is unknown.
- **Revisit if:** operator states the container itself is the intended
  production host (it is ephemeral and has no GPU, so this is not recommended).

## ADR-0003 Phase 0 language and test stack  [ARCH]
- **Date:** 2026-11-21 · **Status:** Accepted (provisional; full decision 5.6 #1 in Phase 1)
- **Choice:** Python ≥3.11 core package, pytest, PyYAML, jsonschema. Scripts
  that must run before installation (hardware inspection, credential presence)
  are standard-library only.
- **Evidence:** The media/ML ecosystem the spec names (faster-whisper,
  PySceneDetect, OpenCV, pyannote) is Python-first [ASSUMPTION A-008 until
  Phase 1 comparison]. Container has Python 3.13, pytest 9.1, ffmpeg 6.1.1 [MEASURED].
- **Revisit if:** Phase 1 comparison (5.6 #1) finds a stage needing another
  runtime (e.g. Node for motion graphics).

## ADR-0004 No stubbed CLI commands  [QA]
- **Date:** 2026-11-21 · **Status:** Accepted
- **Choice:** The CLI registers only implemented commands. Appendix A.6 commands
  appear as each stage lands with tests. Spec 2.7 forbids placeholders that look
  like finished features.

## ADR-0005 Default publishing autonomy L0 until approvals exist  [RIGHTS]
- **Date:** 2026-11-21 · **Status:** Accepted
- **Context:** No platform credentials are present (config/credentials_presence.json).
  TikTok forces private visibility for unaudited clients; YouTube documentation
  is inconsistent on the private-only restriction (EVIDENCE E-001..E-004).
- **Choice:** All platforms start at L0 (prepare-only bundles). L1 is enabled per
  platform once an approved integration and operator consent exist. Spec 11.6
  says default L1/L2. L0 is stricter, so it does not weaken a requirement.

## ADR-0006 Walking-skeleton ASR engine: faster-whisper (provisional)  [ML]
- **Date:** 2026-11-21 · **Status:** Accepted for the skeleton only. Decision 5.6 #4 stays open.
- **Options tried:** pocketsphinx 5.1.1 (bundled en-us model, offline):
  transcript was unrelated to the speech on a clean 11.6 s TTS clip (E-018).
  faster-whisper 1.2.1 (CTranslate2 int8, CPU): tiny.en, base.en and small.en
  got every word right on the same clip (E-013).
- **Choice:** faster-whisper `base.en` int8 as the default in
  `config/settings.example.yaml`. Audio is decoded by FFmpeg into float32 and
  passed as an array, which avoids a PyAV API incompatibility (E-019).
- **Revisit:** Phase 1 benchmark on the operator machine with real gaming audio
  (B-01, B-02). No accuracy claim is made from synthetic speech.

## ADR-0007 Skeleton artefact store: per-source JSON files  [ARCH]
- **Date:** 2026-11-21 · **Status:** Accepted for Phases 0-1. Decision 5.6 #3 (SQLite vs PostgreSQL) stays open.
- **Choice:** each stage writes one JSON artefact under `data/work/<source_id>/`.
  Writes are atomic (temp file + fsync + rename). Each artefact embeds its
  input key = hash(code version, stage version, upstream keys, relevant config).
  A matching key means the stage is skipped on rerun.
- **Why:** this is the smallest thing that gives resumability (P9) and
  inspectable state, and it defers the DB choice until query needs are known.
- **Known limits:** no cross-source queries, no locking for parallel workers.
  Both are needed by Phase 4 (library ranking) and will drive the DB decision.

## ADR-0008 Cloud environment for this repository  [SEC]
- **Date:** 2026-11-21 · **Status:** Accepted (operator approved in the session)
- **Context:** the default cloud environment blocked huggingface.co, so no ASR
  model weights could be downloaded (E-012).
- **Choice:** a personal environment "GTA", scoped to this repository, that adds
  Hugging Face hosts only (huggingface.co, its LFS/Xet CDN hosts and
  us.aws.cdn.hf.co). Package registries were already allowed.
- **Consequence:** CI and the operator machine download models from the same hosts.

## ADR-0009 Publishing route per platform  [GROWTH, RIGHTS]
- **Date:** 2026-11-22 · **Status:** Accepted. Supersedes the platform assumptions in ADR-0005's context (L0 default unchanged).
- **Evidence:** E-020-E-028 (VERIFIED, PLATFORM_LIMITS.md).
- **YouTube (first integration target):** `videos.insert` with OAuth. No audit
  needed at our volume (100 uploads/day default). The unverified-project
  private restriction is gone, so **the adapter must always send
  `privacyStatus` explicitly** (`private` at L1) and must set
  `hasPaidProductPlacement`, `selfDeclaredMadeForKids` and
  `containsSyntheticMedia`. Never rely on defaults.
- **TikTok:** Direct Post's intended-use rules exclude tools for one's own
  accounts (E-024), so no Direct Post audit application is planned. The target
  is the **inbox/draft upload** (`video.upload`): the operator finishes each
  post in the TikTok app, which also satisfies L1/L2 human release. If scope
  approval is refused, TikTok stays at L0 (ready-to-post bundle).
- **Instagram:** Facebook Login for Business variant, so that resumable upload
  of local files avoids public hosting (E-027). This requires a Business or
  Creator account linked to a Page.
- **Twitch:** source only. Clip files only for the operator's own channel or
  channels where the operator is an editor with written creator permission
  (classes A/B).
- **Packaging consequence:** no channel watermark or logo burned into videos
  destined for TikTok (E-025). The render needs per-platform overlays.
- **Revisit if:** TikTok publishes a personal-creator route or app review rejects `video.upload`.

## ADR-0010 Audio-event model for the music screen: YAMNet via LiteRT  [ML, RIGHTS]
- **Date:** 2026-11-22 · **Status:** Accepted (provisional, pending calibration on real footage)
- **Need:** R26 (licensed music in GTA radio) is a top-five risk, and YouTube
  blocks Shorts over 1 min that have any claim (E-031).
- **Options:** AST (BSD-3; ONNX available, but needs Kaldi fbank features
  reimplemented and is about 350 MB); PANNs (Apache-2.0; Zenodo weights not
  reachable); YAMNet TFLite (Apache-2.0, about 4 MB, takes raw 16 kHz audio
  directly, no feature code).
- **Choice:** YAMNet through `ai-edge-litert` (Apache-2.0), part of the `asr`
  extra. Weights are fetched from a pinned URL and verified by sha256 (E-036).
- **Gates:** a candidate is rejected if more than 10 % of its windows score
  Music ≥ 0.30. QA rejects a render with detected music. If the model or
  runtime is missing, everything **fails closed**. Thresholds are hypotheses
  (E-037).
- **Known limits:** a classifier cannot tell licensed music from
  royalty-free music, and quiet music under engine noise may be missed. Mute or
  replace is not implemented, so music means rejection for now.
- **Bonus signal:** explosion/gunshot/laughter/scream/crash scores are stored
  per window for the Phase 4 ranker.
