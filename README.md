# clipops

A local-first, rights-aware system for turning authorised gaming footage into
short-form vertical videos. Specification: `docs/MASTER_PROMPT.md`.

## Status
**Phase 0: walking skeleton done.** Every stage runs crudely end to end on a
synthetic fixture (`clipops demo run`). Gate G0 waits on the operator-machine
hardware report (`docs/BLOCKERS.md` B-01). Output is not publishable: there is
no style engine, no creative review and no contribution test yet.

## Quick start (development)
```bash
pip install -e ".[dev,asr]"      # plus ffmpeg and espeak-ng on PATH
pytest -q
clipops health
clipops demo run                  # synthetic fixture → short + QA + run report
```

## Make shorts from a video (one command)
```bash
uv run python scripts/clip_url.py "<YouTube link or video file>" --rights E --attest "test only"
```
Shorts and a summary land in `out/`. Rights: A = your own footage, B/C = permission or licence
(`--grant file.json`), E = none (your stated basis is recorded).

## Operator: first actions
See `docs/OPERATOR_TODO.md`. The most important:
```bash
python3 scripts/inspect_hardware.py --role operator-machine  # on your own computer, inside the cloned repo
```

## Where things are
`CLAUDE.md` holds the working rules. `docs/PROGRESS.md` holds the latest
checkpoint. `docs/AMENDMENTS.md` records deviations from the specification.
