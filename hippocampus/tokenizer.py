"""tokenizer: configurable FTS pre-tokenization (v1.10).

The SQLite FTS5 virtual table itself always uses `unicode61`; we control
recall quality by how we *pre-split* text into the space-separated tokens
stored in `fts_text` (index side) and built into MATCH queries (query side).
Index and query MUST use the same mode, otherwise tokens never line up.

Modes (memori-inspired):
  - "char"   : one token per CJK char (default, current behaviour). Robust,
               zero-dependency, but low IDF discrimination for Chinese.
  - "bigram" : overlapping CJK character bigrams ("\u673a\u5668\u5b66\u4e60" ->
               "\u673a\u5668 \u5668\u5b66 \u5b66\u4e60"). Better discrimination, still
               zero-dependency.
  - "jieba"  : real word segmentation via jieba; falls back to "bigram"
               automatically when jieba is not installed ("zero hard dep").

Non-CJK runs (ascii words, digits) are kept whole in every mode.
"""
from __future__ import annotations

_CJK_RANGES = (
    (0x4E00, 0x9FFF),
    (0x3400, 0x4DBF),
    (0x3000, 0x303F),
    (0xFF00, 0xFFEF),
)

VALID_MODES = ("char", "bigram", "jieba")

_jieba = None
_jieba_tried = False


def _is_cjk(ch: str) -> bool:
    cp = ord(ch)
    return any(lo <= cp <= hi for lo, hi in _CJK_RANGES)


def normalize_mode(mode) -> str:
    """Coerce a config value to a known mode, defaulting to 'char'."""
    m = (mode or "char")
    m = str(m).strip().lower()
    return m if m in VALID_MODES else "char"


def _runs(text):
    """Yield (is_cjk, run) segments, splitting on whitespace boundaries."""
    cur = []
    cur_cjk = None
    for ch in text:
        if ch.isspace():
            if cur:
                yield cur_cjk, "".join(cur)
                cur = []
                cur_cjk = None
            continue
        c = _is_cjk(ch)
        if cur and c != cur_cjk:
            yield cur_cjk, "".join(cur)
            cur = []
        cur.append(ch)
        cur_cjk = c
    if cur:
        yield cur_cjk, "".join(cur)


def _char_tokens(run):
    return list(run)


def _bigram_tokens(run):
    if len(run) <= 1:
        return [run]
    return [run[i:i + 2] for i in range(len(run) - 1)]


def _load_jieba():
    global _jieba, _jieba_tried
    if _jieba_tried:
        return _jieba
    _jieba_tried = True
    try:
        import jieba  # type: ignore
        _jieba = jieba
    except Exception:
        _jieba = None
    return _jieba


def _jieba_tokens(run):
    jb = _load_jieba()
    if jb is None:
        return _bigram_tokens(run)
    toks = [t.strip() for t in jb.cut(run) if t and t.strip()]
    return toks or _bigram_tokens(run)


def jieba_available() -> bool:
    return _load_jieba() is not None


def tokenize(text: str, mode: str = "char") -> str:
    """Return a space-joined token string for FTS index/query under `mode`.

    Non-CJK runs are kept whole; CJK runs are split per the chosen mode.
    The result is normalized whitespace (single spaces, trimmed).
    """
    if not text:
        return ""
    mode = normalize_mode(mode)
    out = []
    for is_cjk, run in _runs(text):
        if not is_cjk:
            out.append(run)
            continue
        if mode == "char":
            out.extend(_char_tokens(run))
        elif mode == "bigram":
            out.extend(_bigram_tokens(run))
        else:  # jieba
            out.extend(_jieba_tokens(run))
    return " ".join(t for t in out if t)
