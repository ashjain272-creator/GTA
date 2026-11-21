# clipops

A local-first, rights-aware system for turning authorised gaming footage into
short-form vertical videos. Specification: `docs/MASTER_PROMPT.md`.

## Status
**Phase 0 (orientation): ready to close except B-01.** Gate G0 waits on the
operator-machine hardware report (`docs/BLOCKERS.md` B-01). No media pipeline
code exists yet. The next task is the walking skeleton (`docs/ROADMAP.md` P0-12).

## Quick start (development)
```bash
pip install -e ".[dev]"
pytest -m smoke -q
clipops health
```

## Operator: first actions
See `docs/OPERATOR_TODO.md`. The most important:
```bash
python scripts/inspect_hardware.py --role operator-machine   # on your own computer
```

## Where things are
`CLAUDE.md` holds the working rules. `docs/PROGRESS.md` holds the latest
checkpoint. `docs/AMENDMENTS.md` records deviations from the specification.
