"""Smoke v51: embedding bridge cold-start race (v1.29.1).

Production root cause: the engram bridge installs ProxyEmbeddingProvider
during plugin init, BEFORE AstrBot finishes loading its embedding provider
(~16s later). The old code probed dim at construction; an empty probe
raised ValueError -> register_embedding failed -> astrmock embedding was
permanently dropped -> embeddings never flowed through the host.

Fix: ProxyEmbeddingProvider tolerates a cold/empty probe (dim stays 0,
no exception) and resolves dim lazily on the first successful embed().
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


def main():
    from hippocampus.providers import ProxyEmbeddingProvider, ProviderRegistry

    # 1) cold start: backing provider not ready -> fn returns [].
    state = {"ready": False}
    def fn(text):
        return [0.1, 0.2, 0.3, 0.4] if state["ready"] else []

    p = ProxyEmbeddingProvider("astrmock", fn)
    assert p.dim == 0, p.dim                 # no exception, dim deferred
    reg = ProviderRegistry()
    reg.register_embedding("astrmock", p)    # must NOT raise
    assert reg.has_embedding("astrmock")
    print("  cold-start register tolerated (no fail-fast): OK")

    # 2) provider becomes ready -> embed works + dim resolves
    state["ready"] = True
    v = p.embed("hello")
    assert len(v) == 4 and p.dim == 4, (v, p.dim)
    print("  lazy dim resolved on first real embed: OK")

    # 3) warm start: a good probe at construct time still sets dim
    p2 = ProxyEmbeddingProvider("ok", lambda t: [1.0] * 8)
    assert p2.dim == 8, p2.dim
    print("  warm-start dim probe still works: OK")

    # 4) explicit dim hint honored without probing
    probed = {"n": 0}
    def fn3(t):
        probed["n"] += 1
        return [0.0] * 3
    p3 = ProxyEmbeddingProvider("hinted", fn3, dim=16)
    assert p3.dim == 16 and probed["n"] == 0, (p3.dim, probed)
    print("  explicit dim hint skips probe: OK")

    print("v51 OK")


if __name__ == "__main__":
    main()
