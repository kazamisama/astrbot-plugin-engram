"""dedup: text-layer near-duplicate detection (v1.11).

memori-inspired complement to the vector PatternSeparator. The separator
relies on embedding cosine over the *same-session* working-memory window;
that misses two real cases:
  - the default hash embedder has weak semantic discrimination, so
    near-identical text may not score high enough to merge;
  - cross-session / post-restart duplicates never enter the working window.

This module adds a cheap word-level Jaccard check. It reuses the configured
FTS tokenizer (char/bigram/jieba) so the token granularity matches recall,
and is gated behind a high threshold (default 0.9) so it only fires on
genuine near-duplicates. It is *advisory*: service.observe decides what to
do with a hit (merge into the existing engram), reusing the existing merge
path. Disabled by default to preserve current behaviour.
"""
from __future__ import annotations

from .tokenizer import tokenize


def token_set(text: str, mode: str = "char") -> set:
    """Tokenize `text` under `mode` and return the unique token set."""
    if not text:
        return set()
    return set(t for t in tokenize(text, mode).split() if t)


def jaccard(a: set, b: set) -> float:
    """Jaccard similarity of two token sets. 0.0 for two empty sets."""
    if not a and not b:
        return 0.0
    inter = len(a & b)
    if inter == 0:
        return 0.0
    union = len(a | b)
    return inter / union if union else 0.0


def best_duplicate(text: str, candidates, *, mode: str = "char",
                   threshold: float = 0.9):
    """Return (engram, score) of the highest-Jaccard candidate at or above
    `threshold`, or None. `candidates` is an iterable of Engram-like objects
    exposing `.content` / `.summary`."""
    src = token_set(text, mode)
    if not src:
        return None
    best = None
    best_score = 0.0
    for c in candidates:
        ctext = (getattr(c, "content", "") or getattr(c, "summary", "") or "")
        score = jaccard(src, token_set(ctext, mode))
        if score >= threshold and score > best_score:
            best = c
            best_score = score
    if best is None:
        return None
    return best, best_score
