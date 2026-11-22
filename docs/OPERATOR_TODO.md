# Operator TODO

A short, prioritised list of human-only actions. Each item says why it matters
and what it unblocks. Engineering continues on everything else meanwhile.

## Questions (answer once; defaults apply until answered)

| # | Question | Default if unanswered | Why it matters |
|---|---|---|---|
| Q1 | Which footage do you own or have written permission or a licence for, and where is it? | Nothing is authorised (A-002) | Without it, nothing real can be ingested (B-02) |
| Q2 | Which computer will run the system (OS, laptop or desktop)? Can it be inspected? | Unknown (A-009) | Model sizes, encoders, concurrency (B-01) |
| Q3 | Which games are in scope? Is GTA the main one? Should GTA content be monetised? | GTA, non-monetised (A-001, AM-05) | Rockstar permits only non-commercial fan use without a licence (B-06) |
| Q4 | Which platforms and accounts, and who holds them? Is the account-holder an adult? | YT/TikTok/IG, adult holder (A-003, A-011) | Developer approvals and OAuth must be done by the account-holder |
| Q5 | Is any paid service acceptable? Monthly ceiling? | No, USD 0 (A-005) | Hosted models, media hosting for Instagram |
| Q6 | Languages for subtitles? | English (A-004) | Speech model choice |
| Q7 | Weekly review time available? | 60 min (A-007) | Review thresholds and sampling |
| Q8 | Country of residence (for law and data-protection orientation)? | Unknown | Privacy obligations, monetisation and tax notes |
| Q9 | What should the channel be known for (niche, tone)? | Derived from footage | Channel identity guide (11.9) |

## Actions (in priority order)

1. **Run the hardware inspection on your computer** (B-01). About 2 minutes,
   or 12 with the thermal test.
2. **Declare footage and rights** (B-02, Q1).
3. **Create the Google Cloud project and Desktop OAuth client** (B-03 steps 1-3).
   No audit is needed (verified 2026-11-22). This is the first integration target.
4. **Create the TikTok developer app and request only `video.upload`** (B-04).
   You will finish each post in the TikTok app. TikTok's rules exclude
   automated direct posting from personal tools.
5. **Make the Instagram account Business or Creator, link a Facebook Page, and
   create the Meta app** (B-05).
6. **Decide on GTA monetisation** (B-06).
7. **Choose static hosting for the policy pages** (B-07). Not needed until Phase 7.
