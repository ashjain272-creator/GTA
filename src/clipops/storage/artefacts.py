"""Artefact I/O: atomic JSON writes, hashing, per-source work directories."""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any


def sha256_file(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while b := f.read(chunk):
            h.update(b)
    return h.hexdigest()


def write_json(path: Path, data: Any) -> Path:
    """Write JSON atomically so a crash never leaves a half-written artefact."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".tmp_", suffix=".json")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(data, f, indent=2, sort_keys=False)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise
    return path


def read_json(path: Path) -> Any:
    return json.loads(Path(path).read_text())


def source_dir(work_root: Path, source_id: str) -> Path:
    d = work_root / source_id
    d.mkdir(parents=True, exist_ok=True)
    return d
