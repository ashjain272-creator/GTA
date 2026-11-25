# Roadmap (refines spec Chapter 17)

Effort is in sessions (spec 2.14). A task exceeding 2× its estimate triggers a
re-plan. Gates are tagged in Git when passed. Status: ✅ done · ◐ partial ·
☐ open · ⛔ blocked (see BLOCKERS.md).

## Phase 0: Orientation and foundations (est. 1-2 sessions)

| ID | Task | Role | Status | Evidence |
|---|---|---|---|---|
| P0-01 | Repository layout (2.4) | ARCH | ✅ | tree; ADR-0001 |
| P0-02 | MASTER_PROMPT.docx copy and .md conversion verified | WRITER | ✅ | `test_master_prompt_*` |
| P0-03 | Hardware inspection script (portable, real encode tests) | MEDIA | ✅ | scripts/inspect_hardware.py |
| P0-04 | Hardware report of the **operator** machine | MEDIA | ⛔ B-01 | container report only |
| P0-05 | Credential presence check (no values) | SEC | ✅ | config/credentials_presence.json |
| P0-06 | Five ledgers | WRITER | ✅ | docs/ |
| P0-07 | Self-audit → AMENDMENTS.md | all | ✅ | docs/AMENDMENTS.md |
| P0-08 | Knowledge map, DISCOVERY.md | RESEARCH | ✅ (seeded) | docs/ |
| P0-09 | BLOCKERS.md, OPERATOR_TODO.md | GROWTH | ✅ | docs/ |
| P0-10 | CLAUDE.md, smoke tests, CI skeleton | QA | ✅ | tests/unit/test_smoke.py, .github/workflows/ci.yml |
| P0-11 | First checkpoint | WRITER | ✅ | PROGRESS.md |
| P0-12 | Walking skeleton: synthetic fixture → rights gate → ffprobe ingest → faster-whisper ASR → loudness/scene analysis → candidates with gates and rejections → plan → 9:16 render with burned captions → 12 objective QA checks → run report | ARCH | ✅ | `clipops demo run`; reports/demo/20261121T215543Z; tests/e2e |

**Gate G0:** hardware report (⛔ B-01) · knowledge map reviewed ✅ ·
amendments ✅ · blockers listed ✅ · builds and smoke tests pass ✅.
G0 is **not passed** until B-01 clears. Hardware-independent Phase 1 work may
proceed in parallel (17.17: "do not stall the whole project").

### Skeleton follow-ups (found by running it)
- P0-17 ✅ WCAG general-flash QA check (red flash pending).
- P0-18 ✅ Music screen (YAMNet) on candidates and renders, fail-closed (ADR-0010). Next: mute/duck path; calibration on real audio.
- P0-22 ✅ Real-footage hardening night run (ADR-0018/0019): open corpus, event candidates, sentence/cut-aware edges, flash repair, two-pass captions, loudness loop, machine creative review, clip_url one-command tool.
- P0-21 ✅ Editing engine: 5 styles + selection, smart framing, cold open, speed ramps, punch-ins, owned SFX, animated captions, hooks, ranker v1 (ADR-0015-0017).
- P0-20 ✅ L0 bundles per platform with offline publish gate (ADR-0011).
- P0-19 ✅ Licence matrix (docs/LICENCES.md) with an enforcing test.
- P0-13 ✅ `source classify <url>`: class E path producing a permission-request draft, with no download (spec 4.15 acceptance test 1).
- P0-14 Asset registry check: rendering blocked when an unregistered asset is used (spec 4.15 test 3). Not reachable yet because no assets are used.
- P0-15 ✅ Lockfile (uv.lock; 41 tests pass in the locked env) pinning faster-whisper, ctranslate2 and numpy (R31).
- P0-16 ✅ Measure rendered caption bounds against the safe area (QA currently checks configuration only).

## Phase 1: Research and decisions (est. 4-6 sessions)
- P1-01 ◐ Platform docs read at source (YouTube, TikTok, Instagram, Twitch
  API) → PLATFORM_LIMITS.md, E-020-E-028, ADR-0009. Pending: YouTube Shorts
  criteria, IG Reels specs, Twitch ToS, Rockstar page (hosts unreachable, E-029).
- P1-02 Reused-content policy wording per platform (4.7).
- P1-03 Game policy registry v1: Rockstar first; draft Take-Two licence request (B-06).
- P1-04 Licence matrix for candidate models and tools (R17).
- P1-05 Benchmarks on the operator machine (⛔ B-01): ASR engines × model sizes
  on a gaming-audio test set; scene detection; encoders (VMAF availability, AM-12).
- P1-06 Decisions 5.6 #1-#16 as ADRs.
- P1-07 Corpus v0 (synthetic + directly hosted CC) and v1 (operator footage, ⛔ B-02).
- P1-08 Draft privacy policy and terms pages (B-07); YouTube audit and TikTok audit texts.
- P1-09 Competitor/analogue study (DISCOVERY §3).
- **Gate G1** as spec 17.4.

## Phases 2-11
Follow spec 17.5-17.14 unchanged for now. Task-level breakdown is written at the
start of each phase, informed by Phase 1 decisions. The thinnest end-to-end path
(one source, two styles, one platform at L1) precedes breadth (spec 18.2 E1).
