"""Smoke v48: bot identity comes from the platform (v1.26).

  - _bot_actor_id(event) -> event.get_self_id() (e.g. QQ号), fallback "bot".
  - _resolve_bot_name(event) -> bot nickname via get_login_info, cached;
    fallback to the account id, then "bot".
"""
import asyncio
import os
import sys
import types


def _install_stub():
    a = types.ModuleType("astrbot"); ai = types.ModuleType("astrbot.api")
    sm = types.ModuleType("astrbot.api.star"); em = types.ModuleType("astrbot.api.event")
    class Star: ...
    def register(*a, **k):
        def deco(cls): return cls
        return deco
    class Context: ...
    class AstrMessageEvent: ...
    class _MT: ALL = "all"
    class _F:
        EventMessageType = _MT
        def event_message_type(self, *a, **k):
            def deco(fn): return fn
            return deco
        def command(self, *a, **k):
            def deco(fn): return fn
            return deco
        @staticmethod
        def on_llm_request(*a, **k):
            def deco(fn): return fn
            return deco
        @staticmethod
        def on_llm_response(*a, **k):
            def deco(fn): return fn
            return deco
    sm.Star = Star; sm.register = register; sm.Context = Context
    em.filter = _F; em.AstrMessageEvent = AstrMessageEvent; em.EventMessageType = _MT
    sys.modules["astrbot"] = a; sys.modules["astrbot.api"] = ai
    sys.modules["astrbot.api.star"] = sm; sys.modules["astrbot.api.event"] = em


_install_stub()
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class _Bot:
    def __init__(self, nickname):
        self._nick = nickname
        self.calls = 0
    async def call_action(self, action, **kw):
        self.calls += 1
        if action == "get_login_info":
            return {"user_id": 10001, "nickname": self._nick}
        return {}


class _Event:
    def __init__(self, self_id="10001", nickname="小橘", bot=True, platform="aiocqhttp"):
        self._self_id = self_id
        self._platform = platform
        self.bot = _Bot(nickname) if bot else None
    def get_self_id(self):
        return self._self_id
    def get_platform_name(self):
        return self._platform


def main():
    from handlers.format import _bot_actor_id, _resolve_bot_name, _BOT_NAME_CACHE
    _BOT_NAME_CACHE.clear()

    ev = _Event(self_id="10001", nickname="小橘")
    assert _bot_actor_id(ev) == "10001", _bot_actor_id(ev)

    name = asyncio.run(_resolve_bot_name(ev, "10001"))
    assert name == "小橘", repr(name)
    calls_after_first = ev.bot.calls
    name2 = asyncio.run(_resolve_bot_name(ev, "10001"))
    assert name2 == "小橘"
    assert ev.bot.calls == calls_after_first, "nickname not cached"
    print("  bot id + cached nickname: OK")

    class _Bare:
        pass
    assert _bot_actor_id(_Bare()) == "bot"
    _BOT_NAME_CACHE.clear()
    ev2 = _Event(self_id="20002", nickname="")
    nm = asyncio.run(_resolve_bot_name(ev2, "20002"))
    assert nm == "20002", repr(nm)
    print("  fallbacks (no id / no nickname): OK")
    print("v48 PASS")


if __name__ == "__main__":
    main()
