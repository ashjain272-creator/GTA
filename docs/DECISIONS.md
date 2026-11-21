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
