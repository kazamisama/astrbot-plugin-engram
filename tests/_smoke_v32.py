"""Smoke v1.9: quality.py generic-word / empty-summary checks.

Covers:
  - has_generic_terms: detects CN/EN generic placeholders, ignores real names
  - check_summary: warn message for empty + generic, '' for a good summary
  - build_persona integration: a generic summary still writes (warn-only)
"""
import sys, os, tempfile


sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from hippocampus.quality import has_generic_terms, check_summary
from hippocampus.config import MemoryConfig


def banner(m):
    print("\n=== " + m + " ===")


def test_has_generic_terms():
    banner("has_generic_terms")
    assert has_generic_terms("\u8fd9\u4e2a\u7528\u6237\u559c\u6b22\u732b") is True
    assert has_generic_terms("\u5bf9\u65b9\u662f\u4fa6\u63a2") is True
    assert has_generic_terms("the user likes cats") is True
    assert has_generic_terms("someone said hi") is True
    assert has_generic_terms("\u5c0f\u660e\u559c\u6b22\u732b") is False
    assert has_generic_terms("Alice enjoys jazz") is False
    assert has_generic_terms("") is False
    print("  generic detection OK")


def test_check_summary():
    banner("check_summary")
    assert check_summary("") != ""
    assert "empty" in check_summary("")
    assert check_summary("   ") != ""
    g = check_summary("\u8fd9\u4e2a\u7528\u6237\u559c\u6b22\u732b")
    assert g != "" and "generic" in g
    assert check_summary("\u5c0f\u660e\u559c\u6b22\u732b") == ""
    assert "persona" in check_summary("", label="persona")
    print("  check_summary OK")


class _GenLLM:
    def name(self):
        return "stub"

    def chat(self, system, user, **k):
        return '{"summary": "\u8fd9\u4e2a\u7528\u6237\u559c\u6b22\u732b", "tags": ["\u732b"]}'


def _build_service(tmp, llm):
    from hippocampus.service import MemoryService
    cfg = MemoryConfig()
    cfg.sqlite_path = os.path.join(tmp, "hippo.db")
    cfg.enable_persona = True
    cfg.enable_semantic = False
    cfg.enable_prospective = False
    cfg.enable_profile = False
    svc = MemoryService(cfg=cfg)
    svc.llm = llm
    return svc


def test_build_persona_warn_only():
    banner("build_persona warn-only integration")
    tmp = tempfile.mkdtemp()
    svc = _build_service(tmp, _GenLLM())
    for i in range(3):
        svc.observe(session_id="s", actor_id="u1", platform="qq",
                    channel_id="g1",
                    content="\u8c1c\u9898\u5f88\u6709\u8da3 " + str(i))
    p = svc.build_persona("u1")
    # generic summary -> still written (warn-only), persona returned
    assert p is not None, "generic summary should still be written (warn-only)"
    assert svc.get_persona("u1") is not None
    print("  generic summary written despite warn: OK")
    try:
        svc.close()
    except Exception:
        pass


def main():
    test_has_generic_terms()
    test_check_summary()
    test_build_persona_warn_only()
    print("\nv1.9 smoke: ALL PASS")


if __name__ == "__main__":
    main()
