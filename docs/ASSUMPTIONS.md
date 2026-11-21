# Assumption Register

Defaults chosen so the operator is not interrupted. Each has a cost if wrong
and a way to test. Promoted to a decision or retired when evidence arrives.

| ID | Assumption | Reason | Cost if wrong | Test / resolution | Status |
|---|---|---|---|---|---|
| A-001 | The repository name "GTA" means Grand Theft Auto footage is an intended primary source. | Repo name; no other signal | Low: game registry is generic; only risk emphasis shifts | Operator confirms games in scope (Q3 in OPERATOR_TODO) | Open |
| A-002 | No source footage is currently authorised. Everything is class E until the operator declares otherwise. | No rights statement provided | None: the safe default | Operator declares footage and rights class | Open |
| A-003 | Target publishing platforms: YouTube Shorts, TikTok, Instagram Reels; Twitch as source. | Spec 1.2, 3.5 | Medium: wasted approval work on unused platforms | Operator confirms | Open |
| A-004 | Subtitle/transcription language: English only initially. | Spec 2.9 minimum | Medium: ASR model choice changes for other languages | Operator confirms languages | Open |
| A-005 | No paid services; ceiling USD 0. | Principle 6 | Low: may forgo a hosted model that would raise quality | Operator states ceiling | Open |
| A-006 | Operator timezone UTC for scheduling. | No data | Low: schedule offsets | Operator states timezone | Open |
| A-007 | Operator review time: 60 min/week. | Spec 1.7 implies small involvement | Medium: review thresholds too strict or loose | Operator states budget | Open |
| A-008 | Python ecosystem covers the analysis stack. | Common for ASR/vision tooling | Low: per-stage subprocess boundaries allow mixing | Phase 1 decision 5.6 #1 | Open |
| A-009 | Production machine is a single personal computer of unknown OS. | Spec "local-first", "operator's machine" | High if it is a low-end laptop: model sizes change | Operator runs inspection script (B-01) | Open |
| A-010 | GTA in-game radio contains commercially licensed music likely to trigger Content ID-style claims. | Widely reported; not verified in Phase 0 | High if ignored (claims) | Phase 1 research; music detection on owned footage | Open |
| A-011 | Operator is an adult and can complete developer/OAuth steps personally. | Not stated; needed to plan blockers | High if wrong: adult account-holder must be involved (spec 4.11) | Asked once in OPERATOR_TODO Q4 | Open |
