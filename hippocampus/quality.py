"""quality: lightweight text quality checks (v1.9).

Borrowed from memori's pipeline/quality_validator: detect generic
placeholder words ("用户" / "对方" ...) and empty summaries. These are
*warn-only* signals - they never reject a write, they just flag that an
LLM summary probably failed to use a real name / produced nothing useful.
"""
from __future__ import annotations

# Generic placeholders that suggest the LLM did not use a real nickname.
_GENERIC_TERMS = (
    "用户", "对方", "该用户", "这个人", "某人", "他/她",
    "the user", "this user", "someone",
)


def has_generic_terms(text: str) -> bool:
    """True if `text` contains any generic placeholder term."""
    if not text:
        return False
    low = text.lower()
    for term in _GENERIC_TERMS:
        if term.lower() in low:
            return True
    return False


def check_summary(text: str, *, label: str = "summary") -> str:
    """Return a warn message ('' = no issue) for a summary/persona text.

    Warn-only: callers log the message and still write. Flags empty text
    and generic-placeholder usage.
    """
    t = (text or "").strip()
    if not t:
        return "[hippocampus] quality: empty " + label
    if has_generic_terms(t):
        return ("[hippocampus] quality: " + label
                + " uses generic placeholder (no real name?)")
    return ""