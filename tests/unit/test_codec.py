from datetime import UTC, date, datetime

from permafrost import codec, freeze, hash_of, registry
from permafrost.types import build, encode_node, walk

from ..models import Device, Interface, Site


def test_dict_order_does_not_change_encoding():
    assert encode_node(freeze({"a": 1, "b": 2})) == encode_node(freeze({"b": 2, "a": 1}))
    assert hash_of({"a": 1, "b": 2}) == hash_of({"b": 2, "a": 1})


def test_set_order_does_not_change_encoding():
    a = {f"item-{i}" for i in range(50)}
    b = set(sorted(a, reverse=True))  # noqa: C414 - Exercise insertion in a different order.
    assert encode_node(freeze(a)) == encode_node(freeze(b))


def test_different_content_different_hash():
    assert hash_of({"a": 1}) != hash_of({"a": 2})
    assert hash_of([1, 2]) != hash_of((1, 2))
    assert hash_of(1) != hash_of(True) != hash_of(1.0)
    assert hash_of("a") != hash_of(b"a")


def test_hash_is_16_bytes_and_stable():
    h = hash_of({"a": [1, 2]})
    assert len(h) == 16
    # The hash depends only on content, so it is the same in every process.
    assert h == codec.digest(encode_node(freeze({"a": [1, 2]})))


def _payloads(root):
    return {hash_of(n): codec.unpack(encode_node(n)) for n in walk(root)}


def test_decoding_returns_equal_content(collect):
    def make():
        return {
            "n": None,
            "b": True,
            "i": -5,
            "big": 2**70,
            "f": 1.5,
            "s": "x",
            "y": b"\x00",
            "d": date(2026, 10, 24),
            "dt": datetime(2026, 10, 24, 8, 30, tzinfo=UTC),
            "l": [1, (2, 3), "decoding-test"],
            "set": {1, 2},
            "dev": Device(name="decode", interfaces=(Interface(name="e0", vlans=(1, 2)),)),
            "site": Site(name="paris", devices=["decode"]),
        }

    node = freeze(make())
    root_hash = hash_of(node)
    payloads = _payloads(node)
    del node
    collect()
    assert registry.lookup(root_hash, object) is None

    built = {}

    def resolve(h):
        if h not in built:
            built[h] = build(h, payloads[h], resolve)
        return built[h]

    rebuilt = resolve(root_hash)
    assert rebuilt == make()
    assert hash_of(rebuilt) == root_hash
    assert isinstance(rebuilt["dev"], Device) and isinstance(rebuilt["site"], Site)
    assert hash_of(rebuilt["dev"]) == hash_of(make()["dev"])
