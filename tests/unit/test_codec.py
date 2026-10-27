from datetime import UTC, date, datetime
from enum import Enum

from permafrost import FrozenTuple, codec, freeze, hash_of, registry
from permafrost.types import build, encode_node, walk

from ..models import Color, Device, Interface, Item, Level, OtherState, Perm, Site, State


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


def test_enum_scalar_types():
    class Plain(Enum):
        A = "a"

    class Number(float, Enum):
        A = 1.5

    for t in (State, Color, Level, Perm):
        assert codec.is_enum_scalar_type(t)
        assert codec.is_scalar_type(t)
    for t in (Plain, Number, object, str):
        assert not codec.is_enum_scalar_type(t)
    assert codec.is_scalar_type(str)


def test_enum_member_hash_differs_from_its_value_and_other_class():
    assert hash_of({"s": State.PRESENT}) != hash_of({"s": "present"})
    assert hash_of({"s": State.PRESENT}) != hash_of({"s": OtherState.PRESENT})
    assert hash_of(State.PRESENT) != hash_of("present")
    assert hash_of([Level.LOW]) != hash_of([1])


def test_enum_member_decodes_to_a_placeholder():
    payload = codec.unpack(encode_node(freeze([State.PRESENT, Level.HUGE])))
    items = payload[1]
    assert isinstance(items, list)
    first, second = items
    assert type(first) is codec.EnumValue
    assert (first.name, first.value) == ("tests.models:State", "present")
    assert type(second) is codec.EnumValue
    assert (second.name, second.value) == ("tests.models:Level", 2**70)
    assert codec.refs_in(payload) == []


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
            State.PRESENT: [State.ABSENT, Color.RED, Level.HUGE, (Perm.R | Perm.W,)],
            "e": {Level.LOW},
            "item": Item(name="decode", state=State.ABSENT),
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
    (key,) = (k for k in rebuilt if type(k) is State)
    assert key is State.PRESENT
    assert [type(x) for x in rebuilt[State.PRESENT]] == [State, Color, Level, FrozenTuple]
    assert type(rebuilt[State.PRESENT][3][0]) is Perm
    assert type(next(iter(rebuilt["e"]))) is Level
    assert rebuilt["item"].state is State.ABSENT


def test_enum_member_as_the_whole_value_is_rebuilt():
    payload = codec.unpack(encode_node(State.PRESENT))
    assert build(hash_of(State.PRESENT), payload, lambda h: None) is State.PRESENT
