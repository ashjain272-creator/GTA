# Demonstration records

Each subdirectory is one `clipops demo run`: the walking skeleton on a
synthetic, locally generated fixture (`scripts/make_synthetic_fixture.py`).
Files: `summary.json` (outcome), `run_*.json` (full run report, spec A.5),
`candidates.json` (all candidates including rejections and reasons),
`plan.json`, `qa.json` (objective checks), and a contact sheet of the rendered
short (proxy for visual review, spec 2.15). The rendered video itself is not
committed (large media stays in `data/`). Rerun the demo to regenerate it.

These records demonstrate pipeline mechanics only. The fixture is synthetic
TTS on a clean noise bed and carries no information about quality on real
gaming footage.
