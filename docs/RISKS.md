# Risk Register

Seeded from spec Appendix E (R01-R24), rated and extended in Phase 0.
L = likelihood, I = impact (Low/Medium/High). Reviewed at every phase gate.
Owner roles: RIGHTS, ARCH, MEDIA, ML, EDIT, GROWTH, DATA, QA, SEC.

| ID | Risk | L | I | Justification | Mitigation | Trigger | Owner | Status |
|---|---|---|---|---|---|---|---|---|
| R01 | Source rights insufficient → claims, strikes, removal | H | H | No rights evidence exists yet; repo name suggests GTA footage, which carries a publisher layer (R25) | Rights gate; partnership mode; game policy registry; dispute dossier | Any claim or notice | RIGHTS | Open |
| R02 | Reused-content enforcement demonetises or limits channel | H | H | Clip channels are the archetype these policies target | Contribution test; originality index; commentary/restructuring | Policy notice; originality drift | RIGHTS | Open |
| R03 | API approvals delayed or denied | H | M | YouTube needs no audit at our volume (E-020/E-021). TikTok Direct Post intended-use rules exclude own-account tools (E-024), so inbox upload is the only route and its approval is uncertain. Meta app review needs hosted policy pages | Apply in Phase 0; L0 bundles; L1 private drafts | No response within expected lead time | GROWTH | Open |
| R04 | Platform API or policy changes break adapters | M | M | Official docs already self-contradict (E-002, E-003, E-005) | Scheduled re-verification; contract tests | Test drift; announcement | ARCH | Open |
| R05 | Transcription errors produce wrong subtitles | H | H | Gaming audio: crosstalk, game SFX, slang, proper nouns | Correction pass; glossary; confidence flags; review | Subtitle QA failures | ML | Open |
| R06 | Ranker favours loud but not compelling moments | H | M | Loudness is the cheapest signal and the most misleading | Ablations; baselines; reviewer calibration | Reviewer disagreement | ML | Open |
| R07 | Style monotony / template look | M | M | Five fixed styles invite rotation | Selection logic; diversity checks; restraint score | Style share > 60 % | EDIT | Open |
| R08 | Credential leak or unauthorised posting | L | H | No credentials exist yet; risk rises at L1+ | Secrets outside repo; scoped OAuth; revoke runbook; smoke test for secret patterns | Unknown publish; scanner alert | SEC | Open |
| R09 | Prompt injection through transcripts/on-screen text | M | M | Game chat and usernames are attacker-controlled text | Data-not-instruction handling; schema validation; deterministic gates | Anomalous model output | SEC | Open |
| R10 | Duplicate posting after failures | M | M | Retries on network errors are routine | Idempotency keys; platform check before retry | Duplicate detected | ARCH | Open |
| R11 | Disk exhaustion | M | M | Long VODs and intermediates are large; operator disk unknown | Retention policy; admission guard (`min_free_disk_gib`); alerts | Free space below threshold | ARCH | Open |
| R12 | Overheating / throttling on a laptop | M | L | Operator hardware unknown | Thermal test (`--thermal 10`); scheduling | Render slowdown | MEDIA | Open |
| R13 | Flashing content harms viewers | M | H | Explosions/muzzle flash are common in GTA-type footage | WCAG 2.3.1 general-flash check in QA (blocking) since 2026-11-22; red-flash test pending | Flash check failure | QA | Partly mitigated |
| R14 | Misleading edits misrepresent speakers | M | H | Tight cutting of speech can change meaning | Meaning-preservation check; review | Flagged edit | EDIT | Open |
| R15 | Unrealistic revenue expectations | M | M | Monetisation of GTA footage is restricted (R25) | No forecasts; honest ledger | Operator asks for projections | RIGHTS | Open |
| R16 | Learning loop chases noise | H | M | Small audiences give tiny samples (spec S3) | Guardrails; replication; rollback | Metric swings after changes | DATA | Open |
| R17 | Model/tool licence prohibits intended use | M | M | Several diarisation/ASR models are non-commercial or gated | Licence matrix; class F2 review | Licence change | RIGHTS | Open |
| R18 | Operator review burden too high | M | M | Weekly time budget unknown (A-007) | Review interface; thresholds; sampling | Backlog growth | QA | Open |
| R19 | Age/account eligibility blocks steps | M | H | Operator age/jurisdiction unknown; several platforms require adult account-holder for developer/monetisation steps | Identify human-only steps; ask once | Platform refusal | RIGHTS | Open |
| R20 | Single-platform dependency | M | M | Approvals may land on one platform first | Multi-platform design; owned channels | Policy shock | GROWTH | Open |
| R21 | Silent degradation after dependency upgrades | M | M | ML deps change outputs between versions | Pinned lockfiles; staged upgrades; benchmark reruns | Evaluation regression | QA | Open |
| R22 | Documentation drift | M | L | Many docs, many sessions | Doc-drift checker; smoke tests on doc presence | Checker failure | WRITER | Open |
| R23 | Over-engineering delays progress | H | M | Spec is ~400 KB; temptation to build breadth | Walking skeleton first; gates | Phase overrun > 2× estimate | ARCH | Open |
| R24 | Evaluation circularity from model-made labels | H | M | No operator labels yet | Operator labels outrank; held-out sets; flag weak evidence | Agreement report | DATA | Open |
| R25 | **GTA / Rockstar commercial-use restriction.** Rockstar's policy tolerates occasional non-commercial fan use; monetised clips fall outside it without a Take-Two licence (E-007) | H (if GTA footage is used commercially) | H | Directly contradicts any monetisation goal for GTA content | Game policy registry entry for Rockstar; monetisation flag off for Rockstar titles unless licence on file; draft licensing request for operator; diversify games | Any monetisation step on Rockstar footage | RIGHTS | Open, needs operator |
| R26 | **GTA in-game radio / licensed music** triggers automated claims | H | H | GTA radio stations carry commercially licensed tracks [ASSUMPTION A-010, widely reported, unverified here] | YAMNet music screen gates candidates and renders, failing closed (ADR-0010); mute/replace not yet built; prefer radio-off recordings for owned footage | Music detected in candidate | MEDIA | Partly mitigated |
| R27 | **Spoiler / cutscene removal** (Rockstar removes standalone cutscenes and spoilers, E-007) | M | M | Short clips of story moments are effectively standalone cutscenes | Cutscene/story detection; spoiler flag; exclude unless transformed and policy permits | Cutscene detected | EDIT | Open |
| R28 | **Dev environment ≠ production machine.** Decisions made on the container may not transfer | H | M | Container has no GPU and is ephemeral (ADR-0002) | Defer hardware decisions; portable code; operator runs inspection script | Operator hardware report differs materially | ARCH | Open |
| R29 | **Ephemeral container loses uncommitted work and data** | M | M | Container reclaimed after inactivity | Commit/push every increment; no media stored only here | Session reset | ARCH | Open |
| R30 | **Contradictory official platform docs** lead to wrong capacity plans | H | M | E-002, E-003, E-005 | Read live docs and query live limits (e.g. IG `content_publishing_limit`) at runtime rather than hardcoding | Quota error in production | GROWTH | Open |
| R31 | **Upstream API drift in media/ASR libraries** breaks stages silently (e.g. PyAV signature change, E-019) | M | M | Already observed once | Pin versions in a lockfile (Phase 2); FFmpeg-decoded input instead of library decoders; e2e test in CI | e2e failure after dependency update | QA | Open |
| R33 | **Public-by-default uploads**: YouTube now defaults omitted privacyStatus to public and no longer forces unverified projects to private (E-021) | M | H | A missing field would publish publicly at L1 | Adapter always sets privacyStatus explicitly; contract test asserts it; publish gate checks the autonomy level | Any upload request without privacyStatus | SEC | Open |
| R34 | **Channel-wide demonetisation** from a minority of low-contribution shorts: the reused-content policy applies to the channel as a whole and regardless of permission (E-032) | M | H | One templated batch can taint the channel | Contribution test blocks publishing; channel originality index; style diversity checks (R07) | Monetisation review notice | RIGHTS | Open |
| R35 | **Model supply chain**: YAMNet weights come from a third-party mirror (E-036) | L | M | A tampered model could hide music or misbehave | Pinned sha256 verified on every load; replace with the official source when reachable | Hash mismatch | SEC | Open |
| R32 | **Stale cached artefacts** served after code changes | M | H | Observed once in the skeleton (candidates cached across a logic change) | Stage versions in input keys (ADR-0007); bump rule in pipeline.py; test_resume | Output unchanged after a logic change | ARCH | Mitigated |

## Top five (Phase 0 ranking)
1. R01/R25: rights to the footage, especially Rockstar commercial use.
2. R02: reused-content enforcement.
3. R03: API approval lead times.
4. R26: licensed music inside GTA footage.
5. R05: subtitle accuracy on gaming audio.
