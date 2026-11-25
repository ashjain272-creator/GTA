# Amendments: Self-Audit of the Master Prompt (spec 18.3)

Audit performed 2026-11-21, Phase 0. The original `MASTER_PROMPT.docx` is
unmodified (checksum enforced by `tests/unit/test_smoke.py`). Deviations live
here. None weakens a requirement derived from the operating principles or legal
boundaries. Those require operator approval and none is proposed.

Format: **ID · type · spec ref**. Then the finding and the resolution.
Types: CONTRADICTION, INFEASIBLE, UNTESTABLE, OMISSION, ENVIRONMENT, CLARIFICATION.

---

## 1. Environment findings

**AM-01 · CLARIFICATION · 2.4.** The layout is placed at the repository root, not
under `clipops/` (ADR-0001). The Python package is still `clipops`.

**AM-02 · ENVIRONMENT · 1.3 P9, 2.2(3), 2.11, 5.3.** The spec assumes Claude Code
runs on the operator's own machine. This session runs in an **ephemeral cloud
container**, and no operator computer is attached.
Consequences and resolutions:
- The hardware report describes the container (role `cloud-dev-container`).
  Hardware-dependent decisions are deferred (ADR-0002, B-01). The inspection
  script is portable so the operator can run it locally.
- Principle 9 ("state lives on disk") holds only for what is **committed and
  pushed**. Git-ignored `data/` (media, DB) does not survive container reclaim.
  Rule: no artefact needed for resumption may live only in `data/` on this host.
- The "second local backup location" (2.11) cannot be met in the container. It
  is met by the Git remote for code and docs, and is deferred to the operator
  machine for media and DB.
- Network throughput figures from the container are not representative (E-011).

**AM-03 · CLARIFICATION · 2.3, 2.11.** "Main branch must build": in this
environment work is pushed to the designated feature branch
`claude/new-session-ztycbf`. That branch carries the "always green" obligation
until the operator merges. Phase gates are tagged on that branch.

## 2. Contradictions resolved

**AM-04 · CONTRADICTION · 2.2 vs Appendix I(9).** 2.2 forbids feature code before
orientation steps 1-7. Appendix I schedules the walking skeleton in the first
session. Resolution: both hold in sequence. Steps 1-7 finish and commit first,
and the walking skeleton follows (Phase 0, task P0-12 in ROADMAP.md).

**AM-05 · CONTRADICTION (spec vs external rule) · 13, 4.6.** The spec plans
monetisation generally. For Rockstar titles (GTA), the publisher's policy
tolerates *occasional, non-commercial* fan use and routes commercial use to a
Take-Two licence request (E-007). Resolution: the game policy registry gets a
Rockstar entry with `monetisation_permitted: false` unless a licence record
exists. The monetisation module must consult the registry per short.
Monetisation readiness for GTA content is reported as **blocked pending
licence**. This is Principle 1 applied, not a weakening.

**AM-06 · CONTRADICTION · 11.6.** The spec defaults publishing to L1/L2. This
project starts at **L0** until a platform integration is approved (ADR-0005).
L0 is stricter.

**AM-07 · CONTRADICTION · 2.9 vs platform terms.** The corpus may include
"openly licensed" footage, but a Creative Commons licence on a YouTube video
does not by itself authorise downloading it with tools that platform terms
prohibit. Resolution: CC corpus items are acquired only from hosts that serve
the file directly under the licence (e.g. Wikimedia Commons, Internet Archive),
or through a platform's own download feature. VERIFY the YouTube Terms
download clause in Phase 1.

**AM-08 · RESOLVED 2026-11-22 (E-027): resumable local upload with Facebook Login for Business.** · CONTRADICTION (local-first) · 11.3 Instagram. The Instagram
container flow historically fetches media from a public URL, which conflicts
with local-first and adds hosting cost and exposure. Resolution: Phase 1 checks
whether the resumable-upload flow (E-005) avoids public hosting. If it does
not, a short-lived signed URL on operator-approved storage is a paid/hosting
decision for the operator.

## 3. Infeasible or doubtful requirements

**AM-09 · INFEASIBLE (now) · 2.9.** Minimum corpus: 20 videos, 10 h, 200 labelled
moments. No authorised footage exists yet (A-002), and this container cannot
record gameplay. Resolution: corpus v0 is synthetic FFmpeg material (for
pipeline mechanics only, never used for quality claims) plus directly hosted CC
items with per-item licence verification. Quality claims carry sample size and
confidence intervals (2.9 last paragraph). Gate G1's corpus criterion depends on
operator footage (B-02).

**AM-10 · INFEASIBLE (container) · 5.3.** Thermal test, SSD/HDD type, RAM speed and
real network throughput cannot be measured here. The script supports `--thermal`
and records "not measured" with a reason rather than guessing.

**AM-11 · DOUBTFUL · 6.x, 5.6 #7.** On a CPU-only host, dense local
vision-language analysis is likely too slow for multi-hour VODs (HYPOTHESIS, to
be measured). Design implication, already in 5.3's fallback hierarchy:
cheap signals pre-screen regions, and expensive models run only on shortlisted
windows.

**AM-12 · DOUBTFUL · 10.3.** Objective picture QA via VMAF: the container's
FFmpeg lacks `libvmaf` (E-010). Resolution: Phase 1 evaluates the operator
machine's build, a static FFmpeg build with libvmaf (licence check), or
SSIM/PSNR as a documented fallback with a structured warning (spec 2.7
"silent degradation").

## 4. Untestable acceptance criteria rewritten

The originals stay in the spec. These are the operational tests the project
will use.

| ID | Spec ref | Original (abridged) | Objective replacement |
|---|---|---|---|
| AM-13 | 1.8 #3 | Five styles, "chosen by logic for a recorded reason, not rotation" | On ≥30 ranked candidates from ≥5 sources: ≥5 distinct styles selected; every plan has a non-empty `style_reason` referencing ≥2 candidate features; no style exceeds 60 % share (R07); a shuffled-feature control changes ≥30 % of selections (proves features drive choice). |
| AM-14 | 1.8 #4 | "Reviewed against rubric with notes saved" | Every rendered short has a rubric record with all Appendix C dimensions scored and a pass/fail against thresholds in QUALITY_RUBRIC.md. On a ≥20-item sample, operator and model agreement is reported (Cohen's κ with CI), and items failing operator review count as QA escapes. |
| AM-15 | 1.9 | "Cuts feel invisible", "nothing feels templated" | Proxy metrics: no cut within 120 ms of a word midpoint (unless flagged as intentional); audio click detector passes at every cut; cross-short similarity of style parameter vectors below a threshold set in Phase 5; operator sample review. Marked as **partially machine-checkable**, with residual judgement escalated (2.15). |
| AM-16 | 1.8 #5 | Subtitle accuracy meets "thresholds in Chapter 6" | Thresholds are hypotheses (18.2 E2). Report WER and word-timestamp error per corpus item with sample size, against operator-corrected references only. Model-corrected references are flagged weak (R24). |
| AM-17 | 1.8 #6 | "Publishing works end to end to at least one real or sandboxed destination" | A real API call to one platform creates a private/draft item whose platform ID is stored, then is fetched back and compared by hash/duration. "Sandboxed" means a platform-provided sandbox, not a local mock. |

## 5. Omissions found (role walk and discovery, see DISCOVERY.md)

**AM-18 · OMISSION · 4.6, 4.12.** GTA-specific rights layers not covered:
(a) **in-game radio and licensed music** (R26); (b) **GTA Online / roleplay
(e.g. FiveM) servers**, where other players' voices, usernames and characters
appear. Their consent and privacy are a separate layer from the game publisher.
RP server rules may also restrict content. Resolution: the safety screen detects
third-party voices and usernames. Publishing other players' voices requires
evidence of consent or redaction. Add an RP-server policy field to the rights
record.

**AM-19 · OMISSION · 4.9.** **Exploit, glitch and cheat content.** Showing or
teaching exploits may breach game terms and attract enforcement. Resolution:
content flag `exploit_or_cheat`. Such content is excluded by default.

**AM-20 · OMISSION · 4.9, 11.4.** **Mature-content classification.** GTA is
rated for adults. Packaging must always set "not made for kids" and must
evaluate platform age-restriction and advertiser-suitability guidance per
short. Graphic violence or sexual content in a clip triggers the sensitive
content playbook (J.6a).

**AM-21 · OMISSION · 4.7, 13.3.** **Pre-release and leak footage** is removed by
Rockstar regardless of source (E-007). The ingest rights check rejects footage
dated before a title's official release unless it is official publisher
material under licence.

**AM-22 · OMISSION · 4.10.** **Synthetic narration or voice disclosure.** If any
style uses TTS or AI voice, platform AI-content disclosure flags apply. Add to
the publish gate disclosure step.

**AM-25 · CONTRADICTION (spec vs platform rule) · 11.3, 11.6 TikTok.** The spec
assumes automated publishing through each platform's official API. TikTok's
Direct Post intended-use rules exclude tools for one's own accounts (E-024).
Resolution (ADR-0009): use inbox/draft upload, with a human finishing each post
in the app. This is permitted by the platform, keeps a human in the loop, and is
a narrower capability than the spec envisaged.

**AM-26 · CLARIFICATION · 11.4, 8.x.** TikTok forbids integrations from adding
logos, watermarks or promotional text to shared content (E-025). Styles must not
burn channel branding into TikTok renders. Per-platform render variants are
required (spec 8.9 already allows this).

**AM-27 · CLARIFICATION (spec vs platform rule) · 4.5, 4.7, 13.3.** YouTube's
reused-content policy "applies even if you have permission from the original
creator" and is judged channel-wide (E-032). TikTok withholds recommendation
from reused material "without anything new" (E-035). So creator partnership
(spec 4.5) solves **rights**, not **originality**. The contribution test (4.7)
is mandatory for every short in every rights class, including owned footage. A
channel-level originality index (13.3) gates monetisation readiness.
Compilations "with little or no narrative" fail by definition.

**AM-28 · CLARIFICATION · 7.7.** Default maximum short duration stays at or below
60 s. YouTube blocks Shorts over one minute globally when any copyright claim is
active (E-031), and GTA footage carries a radio-music claim risk (R26). Longer
shorts need an explicit plan-level reason and a clean music screen.

**AM-29 · OPERATOR-APPROVED CHANGE TO PRINCIPLE 1 · 1.3, 4.3, 4.4 (2026-11-25).**
The operator instructed that downloading from YouTube be permitted (spec 1.10:
principles may be changed by the operator). Scope, as implemented in
`src/clipops/ingest/acquire.py`:
- Allowed: one YouTube video or Short per URL, via yt-dlp, only when the
  operator declares class A (owned) or class B (written creator permission,
  grant file required).
- Still refused: classes C-F by URL; DRM-protected media; cookies, logins
  or credentials; proxies or IP rotation; rate-limit or bot-check evasion;
  channel or playlist crawling.
- Accepted risk: YouTube's Terms of Service restrict downloading except as
  the service permits or with prior written permission. Older versions named
  YouTube and the rights holders, and the current wording was not fully read
  (R36). Every acquisition records this basis in the run report and the
  rights record.
- Unchanged: the reused-content and originality rules (AM-27) and the
  Rockstar monetisation restriction (AM-05) apply to acquired footage exactly
  as to files.

## 6. Document-level

**AM-23 · CLARIFICATION · X1.** The spec (~394 KB as Markdown) cannot be held in
working context. Sessions read CLAUDE.md, PROGRESS.md and the checkpoint, then
grep `docs/MASTER_PROMPT.md` by section number. No large spec blocks are copied
into project docs.

**AM-24 · CLARIFICATION.** The spec's issue date (2026-11-22) is one day after
this audit (2026-11-21). No impact.

## 7. VERIFY register (39 occurrences, grouped)

The status of each group. Detail goes in EVIDENCE.md as items are checked.

| Group | Spec refs | Phase 0 status |
|---|---|---|
| YouTube Data API quotas, audit, private-upload restriction | 3.5, 11.3, 18.2 X3 | **VERIFIED 2026-11-22** (E-020-E-022). The spec's X3 note is now out of date: the private restriction was reversed on 2026-11-02. Shorts criteria still PENDING |
| TikTok Content Posting API audit and private restriction | 3.5, 11.3 | **VERIFIED** (E-023-E-025); new constraint AM-25 |
| Instagram publishing requirements and limits | 3.5, 11.3 | **VERIFIED** (E-026, E-027); Reels media specs PENDING |
| Twitch clips/VOD access and reuse terms | 3.5, 4.4, 11.3 | Clip download **VERIFIED** (E-028); ToS/clip ownership PENDING (host blocked, E-029) |
| Platform reused-content / transformation wording | 4.7 | **VERIFIED** YouTube (E-032), TikTok (E-035); Instagram PENDING |
| Photosensitive-seizure guideline thresholds | 4.9 | **VERIFIED** WCAG 2.3.1 (E-033); general flash implemented, red flash pending |
| AI/sponsored disclosure labels | 4.10 | Pending |
| Data-protection obligations (jurisdiction unknown) | 4.12 | Pending; depends on Q (jurisdiction) |
| Model licences (diarisation, ASR) | 5.5, 6.4 | ASR **VERIFIED** (E-030, LICENCES.md); diarisation pending |
| Subtitle and caption handling per platform | 6.5, 8.10 | Pending |
| Safe areas per platform UI | 8.9 | Pending |
| Loudness behaviour per platform | 8.11 | Pending |
| Upload codec/bitrate limits; cover-frame support | 9.3, 9.5a | Pending |
| Scheduling/series/playlist support | 11.5 | Pending |
| Analytics availability and data policies | 12.2, 12.11 | Pending |
| Experiment features (title/thumbnail tests) | 12.7 | Pending |
| Monetisation programme rules | 13.x | Pending; Rockstar constraint already found (E-007) |
| Claude Code skill structure | 14.2 | Pending |

## 8. Three weaknesses of this Phase 0 work (spec 2.6 step 7)

1. Platform evidence comes from search summaries, not full page reads. It is
   labelled SECONDARY, but the BLOCKERS steps built on it may need correction.
2. The hardware report is for a host that will not run production. Nothing here
   validates performance on the operator's machine.
3. The GTA-centred risk emphasis rests on an assumption (A-001) inferred from a
   repository name.
