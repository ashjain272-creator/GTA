from __future__ import annotations

import pytest

from clipops.storage.artefacts import read_json, write_json


def test_failed_write_leaves_previous_artefact_intact(tmp_path):
    p = tmp_path / "a.json"
    write_json(p, {"v": 1})
    with pytest.raises(TypeError):
        write_json(p, {"v": object()})          # not serialisable: simulates a crash mid-write
    assert read_json(p) == {"v": 1}
    assert not list(tmp_path.glob(".tmp_*"))       # no partial temp file left behind
