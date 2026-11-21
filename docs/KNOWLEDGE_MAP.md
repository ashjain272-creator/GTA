# Knowledge Map (spec 3.3)

Status: **not started** · **seeded** (initial evidence) · **in progress** ·
**decided** (ADR exists). Candidate technologies are starting points to be
challenged in Phase 1 (spec 5.5). Listing them here is not a decision.

| Area | Why it matters | Key questions | Candidate technologies | Status | Spec |
|---|---|---|---|---|---|
| Containers, codecs, colour, HDR | Wrong pixel format or range ruins output on phones | VFR handling? HDR→SDR tone mapping for HDR captures? | FFmpeg 6.x/7.x, zscale, tonemap | seeded (FFmpeg 6.1.1 measured, E-010) | 6.2, 9.3 |
| Hardware encode/decode | Draft speed; final quality trade-off | Which encoders work on the operator's machine? Quality at bitrate vs x264? | NVENC, QSV, VAAPI, VideoToolbox, AMF; libx264/x265/SVT-AV1 | seeded (container: software only) | 5.3, 9.3 |
| VFR, A/V drift, sample-accurate cuts | Subtitle/audio desync | Normalise to CFR at ingest? Keyframe-aware seeking cost? | FFmpeg `-fps_mode`, intermediate mezzanine | not started | 5.8 |
| Loudness | Platforms normalise; clipping/pumping is audible | Target LUFS per platform (VERIFY)? True-peak ceiling? | `loudnorm` two-pass, `ebur128` | not started | 8.11, 9.5 |
| Mobile recompression | What survives platform transcode | Upload bitrate sweet spot (VERIFY)? | VMAF on round-tripped files | not started | 9.3 |
| ASR on gaming audio | Subtitles are the most visible defect (R05) | WER with game SFX/music/crosstalk? Word timestamps? Glossary biasing for GTA terms? | faster-whisper, whisper.cpp, WhisperX alignment, NeMo/Parakeet (licence check) | not started | 6.4 |
| Diarisation | Who said what in multiplayer | Needed for target footage? Licence of models? | pyannote (gated/licence), NeMo | not started | 6.4, 5.6 #5 |
| VAD, source separation, music detection | Music claims (R26), dialogue clarity | Detect GTA radio music reliably? Separate voice from game audio? | Silero VAD, Demucs, audio taggers (PANNs/AST) | not started | 6.6 |
| Shot/scene detection, motion | Candidate boundaries and pacing | Cuts vs in-game camera changes? | PySceneDetect, FFmpeg `scdet`, optical flow | not started | 6.7 |
| OCR / HUD parsing | Kill feeds, wanted level, mission-passed banners as event signals | Per-game HUD templates? Robust at 720p? | Tesseract, PaddleOCR, template matching | not started | 6.7 |
| Face/facecam detection, tracking, saliency | Reframing 16:9→9:16 (8.9) | Facecam location stable? Subject tracking in fast driving scenes? | MediaPipe, YOLO-class detectors (licence check), OpenCV trackers | not started | 8.9 |
| Vision-language models | Semantic understanding of moments | Affordable on CPU? Sparse sampling sufficient? | Small local VLMs (quantised), optional hosted | not started (doubtful on CPU, AM-11) | 6.7, 5.6 #7 |
| Multimodal embeddings | Duplicate detection | Frame+text embedding choice? | CLIP-class models, perceptual hashes | not started | 7.6 |
| Hooks, pacing, comedic timing, endings | "Exceptional" bar (1.9) | Encodable rules vs learned? | Appendix C/K rubric, operator labels | not started | 8.3-8.4 |
| Subtitle typography and animation | Legibility in sunlight; style fit | libass sufficient vs custom renderer? | ASS/libass, Pillow/Skia overlays | not started | 8.10, 9.4 |
| Reframing layouts | Subject never lost | Split facecam/gameplay vs tracked crop? | FFmpeg crop/overlay, smoothing filters | not started | 8.9 |
| Sound design assets | Styles need SFX/music legally | Which libraries are permissive (CC0)? | Freesound CC0 subset, platform libraries | not started | 8.11, 4.8 |
| Motion graphics | Text and zoom animation | Programmatic tool fit? | FFmpeg expressions, Pillow, Remotion (Node) | not started | 5.6 #11 |
| Platform capabilities | What can be automated at all | Truth tables per platform | Official APIs | **seeded** (E-001-E-006, conflicts noted) | 3.5, 11.3 |
| Reused-content policies | Dominant business risk (R02) | Exact wording per platform (VERIFY) | Primary policy pages | not started | 4.7 |
| Packaging and scheduling | Distribution | Evidence vs folklore (S2) | Own experiments | not started | 11.4-11.5 |
| Small-audience experimentation | Avoid chasing noise (R16) | Minimum detectable effect at our scale? | Bayesian/sequential tests | not started | 12.6-12.7 |
| Copyright / fair use | Orientation only, not legal advice | Jurisdiction (Q8)? | Primary statutes and official guidance | not started | 4.x |
| Game publisher policies | Second rights layer | Per-game monetisation rules | Publisher policy pages | **seeded** (Rockstar E-007, E-008) | 4.6 |
| Music/SFX/font/model licensing | Every asset needs a licence record | Commercial-use compatibility | SPDX, licence matrix | not started | 4.8, 16 |
| Privacy (third-party players, chat) | Usernames and voices in GTA Online/RP (AM-18) | Consent/redaction policy | — | not started | 4.12 |
| Orchestration, job queue, DB | Resumability (P9) | SQLite queue vs workflow engine (E7) | SQLite + simple worker; Prefect/Dagster as comparisons | not started | 5.5, 5.6 #2-3 |
| Secrets | R08 | OS keychain vs encrypted file | `keyring`, OS keychains, age/sops | not started | 15.6 |
| Observability | Silent failures | Structured logs + run reports sufficient? | stdlib logging JSON, SQLite metrics | not started | 15.8 |
| Packaging/deployment | Operator setup in one runbook | uv/pip lockfile vs container | uv lockfile; Docker optional | not started | 16.7 |
| Monetisation programmes | Eligibility; GTA blocked (AM-05) | Rules per platform (VERIFY) | Primary programme pages | seeded (Rockstar constraint) | 13.2 |
| Economics | Honest expectations (B2) | Credible sources only | — | not started | 13.7 |
