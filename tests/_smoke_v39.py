"""Smoke v1.16: set_llm propagates to encoder/extractor/consolidator.

Root-cause regression guard. Before the fix, service.set_llm only swapped
service.llm and left encoder._llm pinned to the construction-time provider
(RuleLLM), so encoder._try_llm_extract always returned None and every
message was stored verbatim via the rule scorer.
"""
import sys, os, tempfile, types


sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from hippocampus.config import MemoryConfig
from hippocampus.llm import LLMProvider, RuleLLMProvider


def banner(m):
    print(chr(10) + "=== " + m + " ===")


class _StubLLM(LLMProvider):
    """Returns valid JSON so encoder._try_llm_extract takes the LLM path."""
    def name(self): return "stub"
    def chat(self, system, user, **kw):
        return ('{"summary": "\u7528\u6237\u504f\u597d\u6458\u8981", '
                '"topics": ["preference"], "entities": [], "importance": 0.2}')


def _svc(tmp):
    from hippocampus.service import MemoryService
    cfg = MemoryConfig()
    cfg.sqlite_path = os.path.join(tmp, "h.db")
    cfg.enable_semantic = False
    cfg.enable_prospective = False
    cfg.enable_profile = False
    cfg.enable_persona = False
    cfg.dedup_enabled = False
    cfg.enable_separation = False
    cfg.tiering_enabled = False
    cfg.metamemory_enabled = False
    return MemoryService(cfg=cfg)


def test_encoder_pinned_to_rule_before_switch():
    banner("before switch: encoder uses RuleLLM (regression baseline)")
    tmp = tempfile.mkdtemp()
    svc = _svc(tmp)
    assert isinstance(svc.encoder._llm, RuleLLMProvider), "fresh encoder should be rule"
    print("  encoder._llm is RuleLLMProvider OK")
    try: svc.close()
    except Exception: pass


def test_set_llm_propagates_to_encoder():
    banner("set_llm swaps encoder._llm so LLM extraction fires")
    tmp = tempfile.mkdtemp()
    svc = _svc(tmp)
    svc.register_llm("stub", _StubLLM())
    svc.set_llm("stub")
    # the crux: encoder must now hold the stub, not RuleLLM
    assert not isinstance(svc.encoder._llm, RuleLLMProvider), "encoder still pinned to rule!"
    assert svc.encoder._llm is svc.llm, "encoder._llm must equal service.llm"
    # end-to-end: observe -> encode should use LLM summary + LLM importance
    e = svc.observe(session_id="s1", actor_id="u1", platform="qq",
                    channel_id="c1", content="\u6211\u7279\u522b\u559c\u6b22\u4e1c\u65b9Project")
    assert e.summary == "\u7528\u6237\u504f\u597d\u6458\u8981", ("summary not from LLM: " + repr(e.summary))
    assert abs(e.importance - 0.2) < 0.2, ("importance not LLM-derived: " + repr(e.importance))
    print("  encoder switched + observe used LLM summary OK")
    try: svc.close()
    except Exception: pass


def main():
    test_encoder_pinned_to_rule_before_switch()
    test_set_llm_propagates_to_encoder()
    print(chr(10) + "v1.16 smoke: ALL PASS")


if __name__ == "__main__":
    main()
