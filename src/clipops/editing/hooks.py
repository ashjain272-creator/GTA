"""Hook text and on-screen context (spec 8.4 hook design, 8.13 context aids, K.6).

Deterministic and grounded: every line shown is either a verbatim quote from the
transcript or a factual label (the game, what is being attempted, taken from the
speaker's own words). Nothing promises what the clip does not contain
(spec 4.10 integrity). These are automated drafts; the publish gate still
requires human review before anything is posted.
"""
from __future__ import annotations

import re

EXCLAIM = re.compile(r"\b(no way|oh my|wow|what|let'?s go|yes|insane|holy|watch this|here we go|actually worked)\b|!", re.I)


def _sentences(words: list[dict]) -> list[list[dict]]:
    out, cur = [], []
    for w in words:
        cur.append(w)
        if re.search(r"[.!?]$", w["text"]):
            out.append(cur)
            cur = []
    if cur:
        out.append(cur)
    return out


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().strip(",")


def best_quote(words: list[dict], payoff_us: int | None, max_words: int = 8) -> dict | None:
    """The most striking short sentence: exclamatory, short, near the payoff."""
    best, best_score = None, -1.0
    for sent in _sentences(words):
        text = _clean(" ".join(w["text"] for w in sent))
        n = len(sent)
        if n < 3 or n > max_words + 4 or not re.search(r"[.!?]$", sent[-1]["text"]):
            continue                                   # quotes must be complete sentences, not fragments
        score = 1.5 * len(EXCLAIM.findall(text)) + (1.0 if 2 <= n <= max_words else 0.0)
        if payoff_us is not None:
            dist = abs(sent[0]["start_us"] - payoff_us) / 1e6
            score += max(0.0, 1.5 - dist / 2)
        score += 0.2 * min(w["confidence"] for w in sent)
        if score > best_score:
            best, best_score = {"text": text, "start_us": sent[0]["start_us"], "end_us": sent[-1]["end_us"]}, score
    return best


def setup_line(words: list[dict], payoff_us: int | None) -> str | None:
    """The speaker's own statement of intent before the payoff (e.g. 'I am going to jump the car...')."""
    pre = [s for s in _sentences(words) if len(s) >= 3 and (payoff_us is None or s[-1]["end_us"] <= payoff_us)]
    intent = [s for s in pre if re.search(r"\b(going to|gonna|watch|let me|try|i'?ll)\b", " ".join(w["text"] for w in s), re.I)]
    pick = (intent or pre or [None])[-1]
    return _clean(" ".join(w["text"] for w in pick)) if pick else None


def make_hook(device: str, words: list[dict], payoff_us: int | None, game: str | None) -> dict:
    quote = best_quote(words, payoff_us)
    setup = setup_line(words, payoff_us)
    if device == "quote" and quote:
        return {"device": "quote", "text": f"“{quote['text']}”", "source": "verbatim transcript quote"}
    if device == "tease" and setup:
        s = setup if len(setup) <= 60 else setup[:57].rsplit(" ", 1)[0] + "..."
        return {"device": "tease", "text": f"“{s}”", "source": "verbatim setup line"}
    if device == "context":
        label = game or ""
        first = next((_clean(" ".join(w["text"] for w in st)) for st in _sentences(words) if len(st) >= 3), None)
        line = setup or (quote["text"] if quote else None) or first
        if line:
            label = (label + " · " if label else "") + (line if len(line) <= 48 else line[:45].rsplit(" ", 1)[0] + "...")
        if label and line:
            return {"device": "context", "text": label, "source": "game from rights record + speaker's own words"}
    if quote:
        return {"device": "quote", "text": f"“{quote['text']}”", "source": "verbatim transcript quote (fallback)"}
    return {"device": "none", "text": "", "source": "no usable speech"}
