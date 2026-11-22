# Blockers

Each entry: what is blocked, why, what the operator must do, exact steps, how
completion is confirmed, and what the system does automatically afterwards.
Platform steps are based on SECONDARY evidence (EVIDENCE.md). Phase 1 re-checks
them against the live docs and updates this file.

---

## B-01 Operator machine not inspected (partial run 2026-11-22, see E-040)
- **Blocks:** hardware-dependent decisions (spec 5.6 #4, #5, #7, #9, #12,
  concurrency), Gate G0 hardware criterion, DoD item 1.
- **Why:** this session runs in a cloud container. No operator computer is attached.
- **Operator steps (on the computer that will run the system).** macOS has
  no `python` command; use `python3`. The script must be run from inside the
  cloned repository, not from the home folder.
  ```bash
  xcode-select --install          # only if git/python3 are missing (installs Apple's command line tools)
  brew install ffmpeg             # needed for the encoder tests (Homebrew: https://brew.sh)
  cd ~ && git clone -b claude/new-session-ztycbf https://github.com/ashjain272-creator/GTA.git
  cd GTA
  python3 scripts/inspect_hardware.py --role operator-machine
  cat docs/HARDWARE_REPORT.md     # paste this output into the session
  ```
  On a laptop, add `--thermal 10` (a 10-minute encode load).
  - Alternative: connect the computer to this session through Remote Control
    in the Claude desktop app, and the inspection runs directly.
- **Confirmation:** `clipops health` shows `hardware:operator-machine-inspected: ok`.
- **Then automatically:** run the Phase 1 benchmarks (ASR, scene detection,
  encoders) on that machine and record decisions.

## B-08 Operator Mac toolchain and disk space
- **Found by:** the first run of the inspection on the operator's Mac mini (E-040).
- **Blocks:** any pipeline run on that machine; encoder tests in the hardware report.
- **Missing:** FFmpeg (no Homebrew to install it); Python ≥ 3.11 (system has
  3.9.6); disk space (6.7 GB free, while media work needs tens of GB).
- **Steps:**
  1. Install Homebrew (official command from brew.sh; asks for your Mac password):
     `/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"`
  2. `brew install ffmpeg uv`
  3. `uv python install 3.12` (used later by `uv sync`)
  4. Free disk space or attach an external SSD for `data/`.
- **Confirmation:** the re-run report shows FFmpeg present, encoder tests run,
  no "older than the project's minimum" line, and free space above 50 GiB on
  the volume used for `data/`.

## B-02 No authorised source footage
- **Blocks:** real ingestion, the evaluation corpus (Gate G1), every quality claim.
- **Why:** Principle 1. No footage has been declared owned, permitted or licensed.
- **Operator steps:** state, for each source: location (folder/file), who
  recorded it, and its class: **A** own recording, **B** creator's written
  permission (attach the grant), **C** licence (attach the text). Own GTA
  recordings are class A for the video, but are still subject to Rockstar's
  policy (B-06).
- **Confirmation:** a rights record exists per source (Phase 2 tooling).
  Until then, a line in OPERATOR_TODO answers is enough.
- **Then automatically:** ingest, analyse and build corpus v1.

## B-03 YouTube API access
- **Blocks:** L1 private uploads and analytics for YouTube.
- **Lead time:** short. **No audit is needed** for our volume: the default is
  100 uploads/day, and unverified projects are no longer forced to private
  (E-020, E-021, verified 2026-11-22).
- **Steps (account-holder; adult where Google requires):**
  1. Google Cloud console → create project → enable *YouTube Data API v3* (and
     *YouTube Analytics API* for metrics).
  2. Configure the OAuth consent screen (External; add your channel's Google
     account as a test user).
  3. Create OAuth client ID of type **Desktop app**. Download the JSON to a
     location **outside** the repo, and set `CLIPOPS_YOUTUBE_CLIENT_SECRETS_FILE`
     to its path.
  4. No audit application is needed unless volume ever exceeds 100 uploads/day.
- **Confirmation:** `python scripts/check_credentials.py` shows
  `present_file_exists`.
- **Then automatically:** an OAuth consent flow in your browser (Claude never
  sees your password), then a private test upload in Phase 7.

## B-04 TikTok Content Posting API
- **Blocks:** TikTok L1 (draft to inbox).
- **Finding (E-024):** TikTok's Direct Post rules exclude "a utility tool to
  help upload contents to the account(s) you or your team manages", so Direct
  Post audit approval is unlikely. Plan: **inbox upload** (`video.upload`). You
  finish each post in the TikTok app (ADR-0009).
- **Steps:** create a TikTok for Developers account → create an app → add
  *Login Kit* and the *Content Posting API* product → request **`video.upload`**
  only → set env vars `CLIPOPS_TIKTOK_CLIENT_KEY` / `_SECRET` outside the repo.
- **If refused:** TikTok stays at L0. The system prepares a ready-to-post file
  plus caption, and you upload it manually in about a minute.

## B-05 Instagram (Meta) publishing
- **Blocks:** Reels L1.
- **Prerequisites:** an Instagram **Business or Creator** account (E-005). If it
  uses Facebook Login, a linked Page, with Page Publishing Authorization completed
  if the Page requires it.
- **Steps:** Meta for Developers → create app → add the Instagram product →
  request `instagram_content_publish` (plus basic permissions) → app review
  needs a hosted privacy policy URL and a screencast (drafted in Phase 7).
  Note the app ID and secret into env vars.
- **Use the Facebook Login for Business variant.** It allows uploading local
  files without public hosting (E-027), but requires a Facebook Page linked to the account.

## B-06 Rockstar / Take-Two licence for monetised GTA content
- **Blocks:** any monetisation of GTA footage (AM-05, R25).
- **Why:** Rockstar's policy covers occasional non-commercial fan use (E-007).
- **Operator decision:** (a) publish GTA content non-monetised, (b) request a
  licence from Take-Two via the copyright contact on Rockstar's policy page
  (the system drafts the request: content description and specific use), or
  (c) prioritise games whose publishers permit monetised video.
- **Then automatically:** a game policy registry entry, and monetisation flags
  per short.

## B-07 Hosted policy pages for app reviews
- **Blocks:** B-04 scope review and B-05 app review (YouTube needs neither at our volume, E-020).
- **Steps:** the operator chooses where to host two static pages (privacy policy,
  terms). Phase 1 drafts both. Hosting is free on many static hosts. Choosing
  one is the operator's decision.
