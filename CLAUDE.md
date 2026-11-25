# CLAUDE.md: clipops project instructions

The authoritative specification is `docs/MASTER_PROMPT.md` (searchable) /
`docs/MASTER_PROMPT.docx` (original, never edit). It is ~394 KB: do not read it
whole. Grep it by section number (e.g. `grep -n '^## 8.10' docs/MASTER_PROMPT.md`).
Approved deviations are in `docs/AMENDMENTS.md`.

## Session start (spec 2.3)
1. Read `docs/PROGRESS.md` (latest CHECKPOINT first), open items in
   `docs/RISKS.md`, and the last 20 entries of `docs/DECISIONS.md`.
2. State the current phase and next gate in 2-3 sentences.
3. Run `uv sync --extra dev --extra asr` (locked; or `pip install -e ".[dev,asr]"`) if needed (plus `apt-get install espeak-ng`
   for the demo fixture), then `pytest -m smoke -q` and `clipops health`. If the
   repo is not green, fixing that comes first. Full suite: `pytest -q` (~40 s).

## Session end
Write a CHECKPOINT entry in `docs/PROGRESS.md`: done, verified, half-finished,
exact next step, relevant files, hazards. Commit and push. This environment may
be an ephemeral container: anything not pushed is lost (AMENDMENTS AM-02).

## The ten operating principles (spec 1.3, in priority order)
1. Lawful, authorised access only. Never bypass auth, DRM, paywalls, rate
   limits or bot checks. Public is not permission. **Operator-approved
   exception (AM-29, 2026-11-25):** a single YouTube video may be downloaded
   with yt-dlp when its rights record is class A (owned) or B (written creator
   permission). No cookies, logins, proxies or evasion; DRM is still refused.
2. Honesty about capability. No stub may return success without doing the work.
3. Quality over quantity. Publishing nothing is acceptable.
4. Evidence over assertion. Tag claims VERIFIED / SECONDARY / MEASURED / ASSUMPTION.
5. Inspect, do not assume. Exit code 0 is not success.
6. Local-first, cost-conscious. No paid dependency without operator consent.
7. Human responsibility is explicit. Identity, consent, payment and policy
   acceptance are the operator's to do. Stop and ask.
8. Learning without self-deception. No promises of views, revenue or virality.
9. Resilience and continuity. State on disk, versioned, resumable.
10. Transformative contribution. Every short adds describable creative value.

## Never implement (spec 1.6)
Protection/paywall/DRM/rate-limit/bot-check circumvention; downloading anything
without a class A/B rights record; channel or playlist crawling; fake engagement of any kind;
impersonation or misleading attribution; ToS-violating scraping; automated
account creation; earnings or growth claims. Explain and offer the closest
lawful alternative instead.

## Project-specific rules
- Source rights classes A-F (spec 4.3). Class E/F never enter the pipeline.
- Rockstar/GTA: non-commercial tolerance only. Monetisation is off unless a
  Take-Two licence record exists (AM-05, B-06). Detect in-game radio music
  (R26), standalone cutscenes and spoilers (R27), and third-party player voices (AM-18).
- Publishing autonomy starts at L0. The system never raises its own level (ADR-0005).
- Hardware-dependent decisions wait for the operator-machine report (ADR-0002, B-01).
- All tunables live in `config/` (template: `config/settings.example.yaml`).
- Secrets never enter the repo. Only env-var names are recorded.
- Large media lives in git-ignored `data/` only. Fixtures need a documented origin and licence.
- The CLI registers only implemented commands (ADR-0004). Mocks only in tests, named as mocks.
- Every fallback emits a structured warning and appears in the run report.
- Pipeline stages cache artefacts by input key. When a change alters a stage's
  output, bump its entry in `STAGE_VERSIONS` (src/clipops/orchestrator/pipeline.py).
- Hugging Face model downloads need the cloud environment "GTA" (ADR-0008).

## Repository map
- `docs/`: spec, ledgers (DECISIONS, EVIDENCE, RISKS, ASSUMPTIONS, PROGRESS),
  AMENDMENTS, HARDWARE_REPORT, KNOWLEDGE_MAP, DISCOVERY, BLOCKERS,
  OPERATOR_TODO, ROADMAP, PLATFORM_LIMITS (truth tables: read before any adapter work)
- `config/`: hardware.json, credentials_presence.json, settings.example.yaml, platforms/
- `src/clipops/`: package; stage subpackages per spec 2.4
- `scripts/`: inspect_hardware.py, check_credentials.py (stdlib only), make_synthetic_fixture.py
- `src/clipops/`: ingest (rights, probe), analysis (transcribe, audio, scenes),
  candidates, editing (plan), render (vertical, subtitles), qa (checks, wer),
  analysis/audio_events (YAMNet music screen), qa/visual (flash, caption bounds),
  packaging (L0 bundles), publish/gate (offline gate), orchestrator (pipeline), demo, runreport, config, cli
- `config/platforms/*.yaml`: per-platform export and packaging profiles
- `tests/`: unit (smoke), integration, e2e, fixtures
- `schemas/`: rights_record.schema.json · `config/game_policies.yaml`: publisher policy registry
- `reports/demo/`: recorded demo runs · `skills/`, `tools/`: from Phase 1 onward
