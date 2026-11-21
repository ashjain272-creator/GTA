"""Word error rate against a reference transcript (spec 6.4 acceptance)."""
from __future__ import annotations

import re

_NUM = {"ok": "okay"}


def normalise(text: str) -> list[str]:
    words = re.sub(r"[^a-z0-9' ]+", " ", text.lower()).split()
    return [_NUM.get(w, w) for w in words]


def wer(reference: str, hypothesis: str) -> dict:
    r, h = normalise(reference), normalise(hypothesis)
    d = list(range(len(h) + 1))
    for i in range(1, len(r) + 1):
        prev, d[0] = d[0], i
        for j in range(1, len(h) + 1):
            cur = d[j]
            d[j] = min(d[j] + 1, d[j - 1] + 1, prev + (r[i - 1] != h[j - 1]))
            prev = cur
    return {"wer": round(d[len(h)] / max(len(r), 1), 4), "errors": d[len(h)],
            "reference_words": len(r), "hypothesis_words": len(h)}
