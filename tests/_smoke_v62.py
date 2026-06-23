"""Smoke v1.45 (BUG-13, persona stamp idempotency).

Repro for the "two diaries per session per day" symptom. The fix
lives in handlers.persona_resolver.stamp_persona_id: it is now
idempotent - the first call resolves and stamps; subsequent calls
return the existing stamp verbatim without re-resolving.

Test cases:
  1. Disabled path is also idempotent (returns "").
  2. Enabled + fresh event: stamp resolves + writes, returns the
     resolved value. (We force a known tier-1 path via a fake
     sp.get_async.)
  3. Enabled + already-stamped event: stamp does NOT re-resolve.
     The second call returns the FIRST call's value even if the
     underlying conversation state has changed (we swap the
     session_service_config between calls to simulate /persona in
     flight, and confirm the bot-reply hook does NOT see the new
     value).
"""
from __future__ import annotations
import os
import sys
import types
import asyncio

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

# --- minimal astrbot stub (persona_resolver + handlers.__init__) ---
_astro = types.ModuleType("astrbot")
_astro_api = types.ModuleType("astrbot.api")
_sp_mod = types.ModuleType("astrbot.api.sp")
_evt_mod = types.ModuleType("astrbot.api.event")
class _AstrMessageEvent: pass
_evt_mod.AstrMessageEvent = _AstrMessageEvent
sys.modules["astrbot.api.event"] = _evt_mod
class _SP:
    """Records the last scope/key; returns whatever session_state holds."""
    def __init__(self):
        self.session_state = {}  # scope_id -> dict
    async def get_async(self, *, scope, scope_id, key, default=None):
        return self.session_state.get(scope_id, {}).get(key, default)
    async def set_async(self, *, scope, scope_id, key, value):
        self.session_state.setdefault(scope_id, {})[key] = value
_SP_INSTANCE = _SP()
_sp_mod.get_async = _SP_INSTANCE.get_async
_sp_mod.set_async = _SP_INSTANCE.set_async
sys.modules["astrbot"] = _astro
sys.modules["astrbot.api"] = _astro_api
sys.modules["astrbot.api.sp"] = _sp_mod
# --- end stub ---


class FakeEvent:
    """Minimal event with get_extra / set_extra backed by a dict."""
    def __init__(self, umo="umo:test:1"):
        self.unified_msg_origin = umo
        self._extra = {}

    def get_extra(self, key, default=None):
        return self._extra.get(key, default)

    def set_extra(self, key, value):
        self._extra[key] = value


class FakeContext:
    pass


def _banner(s):
    print()
    print("=== " + s + " ===")


def test_disabled_returns_empty_and_does_not_set():
    _banner("BUG-13: disabled stamp returns \"\" and does not touch event")
    ev = FakeEvent()
    _SP_INSTANCE.session_state = {"umo:test:1": {"session_service_config": {"persona_id": "should-not-be-used"}}}
    from handlers.persona_resolver import stamp_persona_id
    r = asyncio.run(stamp_persona_id(FakeContext(), ev, enabled=False))
    assert r == "", r
    assert ev.get_extra("hippo_persona_id") is None, ev._extra
    print("PASS disabled_noop")


def test_first_call_resolves_via_tier1():
    _banner("BUG-13: fresh event resolves through session_service_config (tier 1)")
    ev = FakeEvent()
    _SP_INSTANCE.session_state = {
        "umo:test:1": {"session_service_config": {"persona_id": "alice-v1"}}
    }
    from handlers.persona_resolver import stamp_persona_id
    r = asyncio.run(stamp_persona_id(FakeContext(), ev, enabled=True))
    assert r == "alice-v1", r
    assert ev.get_extra("hippo_persona_id") == "alice-v1", ev._extra
    print("PASS first_call_resolves")


def test_second_call_does_not_re_resolve_when_state_changes():
    _banner("BUG-13: stamped event is idempotent even if session_state changes")
    ev = FakeEvent()
    _SP_INSTANCE.session_state = {
        "umo:test:1": {"session_service_config": {"persona_id": "alice-v1"}}
    }
    from handlers.persona_resolver import stamp_persona_id
    ctx = FakeContext()
    # First call: user message flow -> stamps "alice-v1"
    r1 = asyncio.run(stamp_persona_id(ctx, ev, enabled=True))
    assert r1 == "alice-v1", r1
    # Now mutate the session state to simulate /persona flipping to ""
    # (or to "[%None]" sentinel) between user msg and bot reply.
    _SP_INSTANCE.session_state["umo:test:1"]["session_service_config"] = {
        "persona_id": "[%None]"
    }
    # Second call: bot reply flow -> MUST return "alice-v1" (idempotent).
    r2 = asyncio.run(stamp_persona_id(ctx, ev, enabled=True))
    assert r2 == "alice-v1", ("BUG-13 regressed: second stamp overwrote "
                              "with the new value; got " + repr(r2))
    assert ev.get_extra("hippo_persona_id") == "alice-v1", ev._extra
    print("PASS idempotent_across_state_change")


def test_second_call_does_not_overwrite_existing_empty_stamp():
    _banner("BUG-13: empty stamp (\"\") is also sticky")
    ev = FakeEvent()
    _SP_INSTANCE.session_state = {}  # no session_service_config
    from handlers.persona_resolver import stamp_persona_id
    ctx = FakeContext()
    r1 = asyncio.run(stamp_persona_id(ctx, ev, enabled=True))
    assert r1 == "", r1
    # Now wire up a tier-1 persona. Without idempotency, the second
    # call would re-resolve and stamp "bob". With idempotency, "" wins.
    _SP_INSTANCE.session_state["umo:test:1"] = {
        "session_service_config": {"persona_id": "bob"}
    }
    r2 = asyncio.run(stamp_persona_id(ctx, ev, enabled=True))
    assert r2 == "", ("BUG-13 regressed: empty stamp was overwritten by "
                      "later persona; got " + repr(r2))
    print("PASS empty_stamp_is_sticky")


def test_set_extra_failure_on_first_call_does_not_make_second_call_use_default():
    _banner("BUG-13: get_extra returning None triggers resolve; non-None skips")
    # This guards the "is not None" check in stamp_persona_id.
    ev = FakeEvent()
    # get_extra returns None for "hippo_persona_id" (never set)
    assert ev.get_extra("hippo_persona_id") is None
    # ...which should trigger the resolve path; the resolve returns ""
    # because no tier-1/2/3 hit in this stub. Then set_extra lands.
    _SP_INSTANCE.session_state = {}
    from handlers.persona_resolver import stamp_persona_id
    r1 = asyncio.run(stamp_persona_id(FakeContext(), ev, enabled=True))
    assert r1 == "", r1
    assert ev.get_extra("hippo_persona_id") == "", ev._extra
    # Now add a tier-1. Second call should still return "".
    _SP_INSTANCE.session_state["umo:test:1"] = {
        "session_service_config": {"persona_id": "carol"}
    }
    r2 = asyncio.run(stamp_persona_id(FakeContext(), ev, enabled=True))
    assert r2 == "", r2
    print("PASS get_extra_None_triggers_resolve")


def main():
    test_disabled_returns_empty_and_does_not_set()
    test_first_call_resolves_via_tier1()
    test_second_call_does_not_re_resolve_when_state_changes()
    test_second_call_does_not_overwrite_existing_empty_stamp()
    test_set_extra_failure_on_first_call_does_not_make_second_call_use_default()
    print()
    print("ALL v62 PASS")


if __name__ == "__main__":
    main()
