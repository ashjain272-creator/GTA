# Platform Limits: Truth Tables (spec 3.5, 11.3)

The single source of truth for what each platform permits through official
interfaces. Status per row: **VERIFIED** (primary source read, date and page
below) · **SECONDARY** · **PENDING** (not yet read at source).
Re-check every 90 days or when an adapter test drifts. Evidence IDs refer to
docs/EVIDENCE.md.

Last full pass: 2026-11-22.

---

## YouTube (Shorts via YouTube Data API v3)

| Question | Answer | Status | Source |
|---|---|---|---|
| Can the system upload? | Yes: `videos.insert`, with OAuth consent from the channel owner | VERIFIED | videos/insert (updated 2026-11-12) |
| Upload quota | Separate **Video Uploads** bucket: **100 calls/day by default, cost 1 unit per call**. All other methods share 10,000 units/day. Quotas reset at midnight Pacific. | VERIFIED (E-020) | determine_quota_cost; quota_and_compliance_audits (both updated 2026-11-12); revision history 2026-06-01 |
| Private-only restriction for unverified projects? | **No longer.** Revision history 2026-11-02: uploads from unverified projects "are no longer restricted to private viewing mode", reversing the 2020-07-28 policy. If `status.privacyStatus` is omitted, the video defaults to **public**. | VERIFIED (E-021) | revision history (updated 2026-11-17); videos/insert |
| Is an audit needed? | Only to raise quota above the defaults (Audit and Quota Extension Form). 100 uploads/day exceeds this project's needs. | VERIFIED | quota_and_compliance_audits |
| New mandatory fields | `paidProductPlacementDetails.hasPaidProductPlacement` **no longer defaults to false** (revision 2026-11-16). The adapter must set it explicitly. `status.containsSyntheticMedia` exists for altered/synthetic content. `status.selfDeclaredMadeForKids` must be set (always false for GTA content, AM-20). | VERIFIED (E-022) | revision history |
| Shorts classification criteria (duration, aspect) | Not read at source (YouTube Help Center host not reachable from this environment) | PENDING | — |
| What a human must do | Create a Google Cloud project, enable the API, configure the consent screen, create a Desktop OAuth client, and authorise in the browser | — | BLOCKERS B-03 |
| Adapter safety rule | Always send `privacyStatus` explicitly: `private` at L1, never rely on the public default | DECISION ADR-0009 | — |

## TikTok (Content Posting API)

| Question | Answer | Status | Source |
|---|---|---|---|
| Direct Post (`video.publish`) for unaudited clients | All content restricted to private (`SELF_ONLY`); at most **5 users per 24 h**; posting accounts must be **set to private at the time of posting** | VERIFIED (E-023) | content-sharing-guidelines (updated 2026-08-04); get-started |
| Audit eligibility for this project | **Doubtful.** "Intended Use" lists as **not acceptable**: "A utility tool to help upload contents to the account(s) you or your team manages", and "An app that copies arbitrary contents from other platforms to TikTok". A personal clip operation matches the first description. | VERIFIED (E-024) | content-sharing-guidelines |
| Inbox / draft upload (`video.upload`) | `POST /v2/post/publish/inbox/video/init/`. The video lands in the creator's inbox and the creator completes the post in the TikTok app. Rate limit: **6 requests/min per access token**. The private-only restriction is stated for Direct Post, not for inbox upload. Whether app review grants `video.upload` to a personal tool is unknown. | VERIFIED (mechanics), PENDING (approval) | upload-video reference (updated 2026-08-04); scopes |
| Posting cap (Direct Post) | About 15 posts per creator per 24 h, shared across all API clients, plus a per-client active-creator cap | VERIFIED | content-sharing-guidelines |
| Required UX if Direct Post is ever used | Show creator nickname; privacy dropdown with **no default**; interaction toggles off by default; commercial-content disclosure; music-usage consent text; preview; explicit consent before upload; status polling | VERIFIED | content-sharing-guidelines |
| Watermarks | Apps must not add brand names, logos, watermarks, links or promotional text to content shared to TikTok | VERIFIED (E-025) | content-sharing-guidelines |
| Upload transfer | `FILE_UPLOAD` (chunked from a local file: chunks 5-64 MB, final up to 128 MB, at most 1,000) or `PULL_FROM_URL` (only from a domain whose ownership is verified) | VERIFIED | media-transfer-guide (updated 2026-08-04) |
| Media limits | MP4 (recommended)/WebM/MOV; H.264 (recommended)/H.265/VP8/VP9; 23-60 fps; 360-4096 px per side; up to 10 min via API; max 4 GB | VERIFIED | media-transfer-guide |
| What a human must do | Developer account, app with Login Kit and the Content Posting product, scope request, and authorisation in the browser. Finishing each inbox post in the app is also human. | — | BLOCKERS B-04 |

## Instagram (Reels via Instagram Platform API)

| Question | Answer | Status | Source |
|---|---|---|---|
| Account type | Instagram **professional** account (Business or Creator) | VERIFIED (E-026) | content-publishing (updated 2026-10-20) |
| Two API variants | (1) **Facebook Login for Business**: host graph.facebook.com, permissions `instagram_basic` + `instagram_content_publish` (+ `pages_read_engagement`), connected Page; **PPA** must be complete if the Page requires it. (2) **Business Login for Instagram**: host graph.instagram.com, permissions `instagram_business_basic` + `instagram_business_content_publish` | VERIFIED | content-publishing |
| Local file without public hosting? | **Yes, with Facebook Login for Business only**: `upload_type=resumable`, then POST the local file to `rupload.facebook.com/ig-api-upload/...`. Otherwise "media must be hosted on a publicly accessible server". | VERIFIED (E-027) | content-publishing. Resolves AMENDMENTS AM-08 |
| Rate limit | **100 API-published posts per 24 h moving window** (content-publishing, updated 2026-10-20). The older `content_publishing_limit` reference (updated 2024-07-23) still says `quota_total` 50. Use the newer page, and query `GET /<IG_ID>/content_publishing_limit` at runtime instead of hardcoding (R30). | VERIFIED (conflict noted) | both pages |
| App review | Needed for the publish permissions. A hosted privacy-policy URL is required. | SECONDARY | E-005 |
| Reels media specifications | Not extracted in this pass | PENDING | — |
| What a human must do | Convert to a professional account, link a Page (variant 1), create the Meta app, pass app review, authorise in the browser | — | BLOCKERS B-05 |

## Twitch (source platform)

| Question | Answer | Status | Source |
|---|---|---|---|
| Clip metadata | Get Clips (by broadcaster, game or ID) | VERIFIED | API reference, clips |
| Clip file download | **Get Clips Download** `GET /helix/clips/downloads`: user token with `editor:manage:clips` or `channel:manage:clips`, or an app token where that user has authorised the scope. **Only the broadcaster or their editors**: 403 "The user is not an editor for the specified broadcaster". Up to 10 clip IDs per call; 100 requests/min; URLs are temporary (landscape and portrait variants). | VERIFIED (E-028) | dev.twitch.tv/docs/api/reference/clips |
| Implication | Technically consistent with rights classes A (own channel) and B (operator made editor by a consenting creator). The API gives no route to other creators' clip files. | DECISION | spec 4.3 |
| Clip ownership and republishing terms | Not read: the Terms of Service redirect to legal.twitch.com, which this environment does not allow | PENDING | — |
| VOD download | No official endpoint found in the reference | SECONDARY | E-006 |

## Rockstar Games (game publisher layer)

| Question | Answer | Status | Source |
|---|---|---|---|
| Video policy | Occasional non-commercial fan use tolerated. Monetised use needs a Take-Two licence. Cutscenes, spoilers, isolated in-game TV and pre-release/leak footage are removed. | SECONDARY (E-007) | The site returned an empty reply to this environment and is outside the fetch tool's allowed hosts. The operator or a later session must read it directly. |
