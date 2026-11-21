# Discovery (spec 3.9)

Classification: **now** (adopt now) · **later** · **reject** (with reason) ·
**operator** (needs the operator). Phase 0 pass. The competitor study (exercise 3)
is deferred to Phase 1 research because it needs sources.

## 1. Role walk: what a top practitioner would insist on

| Role | Item not in the spec (or under-weighted) | Class |
|---|---|---|
| Media engineer | Ingest normalises to a CFR mezzanine with a recorded original-to-mezzanine timestamp map, so subtitle times can be traced back to the source | now (Phase 2) |
| Media engineer | Detect HDR captures (common on modern consoles/PC) and tone-map deliberately; never let HDR metadata leak into SDR uploads | now |
| ML engineer | A GTA vocabulary list (place names, vehicle names, slang) for ASR prompting and correction | now (per-game glossary) |
| Editor | Respect the game's own "beats": mission-passed and wasted screens, and wanted-level changes, are natural payoff/ending markers | later (HUD templates) |
| Sound designer | Radio-music detection before any other audio work, since a single claim outweighs any mix improvement (R26) | now |
| Rights analyst | Per-title policy records that carry a `last_checked` date and the exact policy URL | now |
| Rights analyst | Third-party players' voices and usernames in multiplayer and RP footage (AM-18) | now |
| Growth strategist | Series structure (recurring formats) usually beats one-off clips for channel identity. This is a hypothesis to be measured | later |
| Data analyst | Pre-register every experiment's metric and stopping rule before it starts | now (Phase 8 design) |
| QA lead | A "QA escape" log: every defect found after publish feeds back into a new automated check | now |
| Security | OAuth tokens scoped to the minimum, and a single kill switch (`publish pause --all`) tested in CI | later (Phase 7) |
| Technical writer | Every doc names its owner role and last-review date, enforced by a doc-drift check | later |

## 2. Pre-mortem: the project failed after six months. Why?

| # | Plausible cause | Mitigation (risk ID) |
|---|---|---|
| 1 | Channel struck or demonetised for reused content | Contribution test, partnership sourcing (R02) |
| 2 | Content ID claims from GTA radio music | Music detection plus mute/replace (R26) |
| 3 | Rockstar takedowns of monetised or cutscene/spoiler clips | Policy registry, cutscene/spoiler detection (R25, R27) |
| 4 | Platform API approval never granted, so the operator posts manually and gives up | L0 bundles make manual posting a 1-minute task; apply early (R03) |
| 5 | Subtitles visibly wrong | Correction pass, glossary, confidence-gated review (R05) |
| 6 | Shorts all look the same | Style diversity checks (R07) |
| 7 | Operator overwhelmed by review queue | Thresholds, sampling, time budget (R18) |
| 8 | Hardware too slow for multi-hour VODs | Pre-screening; measured capacity (AM-11, R28) |
| 9 | Work lost between sessions or containers | Commit/push discipline; checkpoints (R29) |
| 10 | Project stalled building infrastructure | Walking skeleton first (R23) |

## 3. Competitor/analogue study
Deferred to Phase 1 (needs research budget). Scope: professional clipping
channels, esports highlight teams, commercial auto-clippers. Extract workflow
practices and quality markers, not branding.

## 4. Silent-failure brainstorm by stage (detection added)

| Stage | Silent wrong output | Detection |
|---|---|---|
| Ingest | VFR source mis-timed; audio track picked wrong (commentary vs game) | Probe all streams; duration/drift check; track-role classification recorded |
| Transcription | Hallucinated text during music/silence | VAD gating; repeated-phrase detector; confidence floor |
| Audio analysis | Music undetected under engine noise | Calibration clips with known music |
| Visual analysis | Scene detector fires on every camera cut in driving | Per-genre thresholds; precision measured on labelled set |
| Candidates | Only loud moments surface | Signal-ablation report (R06) |
| Boundaries | Punchline cut off | End-boundary rule: never inside a speech segment; check reaction tail |
| Reframing | Subject outside the crop | Per-frame subject-in-crop check on sampled frames |
| Subtitles | Burned text in UI-covered zone | Safe-area check per platform |
| Render | Exit 0 with black frames or silence | blackdetect/silencedetect in QA |
| Packaging | Title promises what the clip lacks | Claim-to-content consistency review |
| Publish | Duplicate after retry | Idempotency key; platform lookup (R10) |
| Analytics | Metric definitions changed by platform | Schema/version check on ingest |

## 5. Adjacent disciplines

| Item | Class |
|---|---|
| Flashing/photosensitivity check (explosions, muzzle flashes) | now (R13) |
| Captions as accessibility: speaker labels and sound cues ([explosion]) for deaf viewers | now (subtitle schema supports cue types) |
| Localisation of subtitles | later (operator Q6) |
| Brand safety: violence, language intensity tags per short | now (AM-20) |
| Community management: drafted replies only, never auto-posted | later |
| Archival: keep masters and edit plans so any short can be re-rendered | now (provenance) |

## 6. Opportunity scan

| Opportunity | Class |
|---|---|
| Owned-footage path: the operator records their own GTA sessions with radio off and voice on a separate track. This yields the cleanest rights and the best audio | operator (strongly recommended) |
| Creator-partnership mode as the main growth path (B1) | operator |
| Evergreen library re-use with refreshed packaging | later |
| Cover-frame A/B testing where a platform offers it natively | later (VERIFY availability) |
| Compilation shorts ("top 3 crashes this week") from approved candidates | later |
| Real-time clipping from live streams | reject for now: separate project phase per K.10 |
