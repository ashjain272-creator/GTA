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


def _phrases(words: list[dict], max_words: int = 7) -> list[list[dict]]:
    """For unpunctuated transcripts: phrases split at pauses >= 0.45 s (or every max_words words)."""
    out, cur = [], []
    for w in words:
        if cur and (w["start_us"] - cur[-1]["end_us"] >= 450_000 or len(cur) >= max_words):
            out.append(cur)
            cur = []
        cur.append(w)
    if cur:
        out.append(cur)
    return out


FUNCTION = {"the", "a", "an", "to", "of", "and", "or", "but", "that", "this", "is", "are", "was", "very", "can", "if",
            "so", "like", "um", "uh", "just", "it", "i", "in", "on", "at", "for", "with", "my", "your", "be"}


def _norm(t: str) -> str:
    return re.sub(r"[^a-z0-9']", "", t.lower())


def best_phrase(words: list[dict], payoff_us: int | None, min_n: int = 3, max_n: int = 7) -> dict | None:
    """Unpunctuated speech: the best 3-7 word span. Rewards exclamations and lines the speaker repeats;
    penalises spans that start/end on function words, stutters and fillers."""
    toks = [_norm(w["text"]) for w in words]
    counts: dict[str, int] = {}
    for n in range(min_n, max_n + 1):
        for i in range(len(toks) - n + 1):
            k = " ".join(toks[i:i + n])
            counts[k] = counts.get(k, 0) + 1
    best, best_score = None, 0.0
    for n in range(min_n, max_n + 1):
        for i in range(len(words) - n + 1):
            span = words[i:i + n]
            if any(span[j + 1]["start_us"] - span[j]["end_us"] > 700_000 for j in range(n - 1)):
                continue                                   # don't bridge a long pause
            t = toks[i:i + n]
            text = " ".join(w["text"] for w in span)
            score = 1.5 * len(EXCLAIM.findall(text)) + (1.2 if counts.get(" ".join(t), 0) >= 2 else 0.0)
            score -= 1.5 * (t[0] in FUNCTION and t[0] not in ("what", "oh")) + 1.5 * (t[-1] in FUNCTION)
            score -= 1.0 * any(t[j] == t[j + 1] and t[j] not in ("no", "yes", "go") for j in range(n - 1))
            score -= 1.0 * any(x in ("um", "uh", "erm") for x in t)
            if payoff_us is not None:
                score += max(0.0, 1.0 - abs(span[0]["start_us"] - payoff_us) / 4e6)
            score += 0.15 * n                               # prefer the fuller line when equal
            if score > best_score:
                best, best_score = {"text": _clean(text), "start_us": span[0]["start_us"], "end_us": span[-1]["end_us"],
                                    "score": round(score, 2)}, score
    return best if best and best_score >= 2.0 else None


def best_quote(words: list[dict], payoff_us: int | None, max_words: int = 8) -> dict | None:
    """The most striking short sentence: exclamatory, short, near the payoff.
    Unpunctuated transcripts use best_phrase instead of sentence splitting."""
    sents = _sentences(words)
    punctuated = any(re.search(r"[.!?]$", s[-1]["text"]) for s in sents)
    if not punctuated:
        return best_phrase(words, payoff_us)
    units = sents
    best, best_score = None, -1.0
    for sent in units:
        text = _clean(" ".join(w["text"] for w in sent))
        n = len(sent)
        if n < 3 or n > max_words + 4 or (punctuated and not re.search(r"[.!?]$", sent[-1]["text"])):
            continue                                   # quotes must be complete sentences (or whole phrases), not fragments
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
        sents = _sentences(words)
        punctuated = any(re.search(r"[.!?]$", x[-1]["text"]) for x in sents)
        first = next((_clean(" ".join(w["text"] for w in st)) for st in sents if len(st) >= 3), None) if punctuated else None
        options = [x for x in (setup, quote["text"] if quote else None, first) if x]
        line = next((x for x in options if len(x) <= 48), None) or (options[0] if options else None)
        if line and len(line) > 48:                    # too long: cut at a clause boundary when there is one
            clause = re.match(r"^(.{12,46}?[,;:])\s", line)
            line = clause.group(1)[:-1] + "..." if clause else line[:45].rsplit(" ", 1)[0] + "..."
        if line:
            label = (label + " · " if label else "") + line
        if label and line:
            return {"device": "context", "text": label, "source": "game from rights record + speaker's own words"}
    if quote:
        return {"device": "quote", "text": f"“{quote['text']}”", "source": "verbatim transcript quote (fallback)"}
    return {"device": "none", "text": "", "source": "no usable speech"}
