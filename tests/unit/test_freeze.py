"""Scenarios of specs/frozen-values/spec.md."""

from dataclasses import dataclass as std_dataclass

import pytest
from pydantic import BaseModel, ConfigDict

from permafrost import (
    FrozenDict,
    FrozenList,
    FrozenTuple,
    UnsupportedTypeError,
    equal,
    freeze,
    hash_of,
    register_type,
    registry,
)

from .. import models
from ..models import Device, Interface, Site


def test_store_a_nested_value():
    value = {"devices": [Device(name="r1", interfaces=(Interface(name="eth0", vlans=(10, 20)),))]}
    frozen = freeze(value)
    assert frozen == value
    assert isinstance(frozen, FrozenDict)
    assert isinstance(frozen["devices"], FrozenList)
    assert isinstance(frozen["devices"][0].interfaces, FrozenTuple)


def test_reject_an_unsupported_type():
    class Opaque:
        pass

    with pytest.raises(UnsupportedTypeError, match="Opaque"):
        freeze({"a": [Opaque()]})


def test_reject_models_that_are_not_frozen():
    @std_dataclass
    class Mutable:
        a: int

    class MutableModel(BaseModel):
        a: int

    with pytest.raises(UnsupportedTypeError, match="frozen"):
        freeze(Mutable(1))
    with pytest.raises(UnsupportedTypeError, match="frozen"):
        freeze(MutableModel(a=1))


def test_reject_slotted_dataclass_without_weak_references():
    @std_dataclass(frozen=True, slots=True)
    class NoWeakref:
        a: int

    with pytest.raises(UnsupportedTypeError, match="FrozenModel"):
        freeze(NoWeakref(1))


def test_standard_frozen_dataclass_without_slots_is_accepted():
    @std_dataclass(frozen=True)
    class Plain:
        a: list[int]

    node = freeze(Plain([1]))
    assert isinstance(node, Plain) and node.a == [1] and isinstance(node.a, FrozenList)


def test_change_the_input_after_storing_it():
    original = {"a": {"b": [1]}}
    frozen = freeze(original)
    original["c"] = 3
    original["a"]["b"].append(2)
    assert frozen == {"a": {"b": [1]}}


def test_read_back_a_pydantic_dataclass():
    d = Device(name="r1")
    frozen = freeze(d)
    assert type(frozen) is Device
    assert frozen == d


def test_read_back_a_pydantic_model():
    s = Site(name="paris", devices=["r1"])
    frozen = freeze(s)
    assert type(frozen) is Site
    assert frozen == s
    assert isinstance(frozen.devices, FrozenList)


def test_model_without_mutable_fields_is_reused():
    i = Interface(name="reuse-me", vlans=(1,))
    assert freeze(i) is freeze(i)


def test_update_a_field_without_validation():
    from permafrost import set_in

    models.POST_INIT_CALLS.clear()
    d = Device(name="r1")
    assert models.POST_INIT_CALLS == ["r1"]
    frozen = freeze(d)
    updated = set_in(frozen, ("site",), "lyon")
    assert updated.site == "lyon"
    assert models.POST_INIT_CALLS == ["r1"]


def test_same_content_in_a_different_order():
    assert hash_of({"a": 1, "b": 2}) == hash_of({"b": 2, "a": 1})
    assert equal({"a": 1, "b": 2}, {"b": 2, "a": 1})


def test_different_content():
    assert hash_of({"a": 1}) != hash_of({"a": 2})


def test_same_items_in_different_collection_types():
    assert hash_of([1, 2]) != hash_of((1, 2))
    assert not equal([1, 2], (1, 2))


def test_same_sub_value_in_two_keys():
    a = freeze({"x": {"shared": [1, 2]}, "y": 1})
    b = freeze({"z": {"shared": [1, 2]}})
    assert a["x"] is b["z"]


def test_identical_values_are_one_object():
    assert freeze({"q": [1]}) is freeze({"q": [1]})


def test_value_that_nothing_refers_to_is_freed(collect):
    node = freeze({"freed": {"inner": [1, 2, 3]}})
    hashes = [hash_of(node), hash_of(node["freed"]), hash_of(node["freed"]["inner"])]
    del node
    collect()
    assert all(registry.lookup(h, object) is None for h in hashes)


def test_frozen_input_is_returned_as_is():
    node = freeze({"a": [1]})
    assert freeze(node) is node
    assert freeze(node["a"]) is node["a"]


def test_store_an_object_with_a_registered_handler():
    class Point:
        __slots__ = ("__weakref__", "x", "y")

        def __init__(self, x, y):
            object.__setattr__(self, "x", x)
            object.__setattr__(self, "y", y)

        def __setattr__(self, name, value):
            raise AttributeError("read-only")

        def __eq__(self, other):
            return isinstance(other, Point) and (self.x, self.y) == (other.x, other.y)

        __hash__ = None  # type: ignore[assignment]

    register_type(Point, name="tests.Point", encode=lambda p: (p.x, p.y), decode=lambda t: Point(*t))
    frozen = freeze({"origin": Point(0, 1)})
    assert isinstance(frozen["origin"], Point)
    assert frozen["origin"] == Point(0, 1)
    assert hash_of(frozen) == hash_of({"origin": Point(0, 1)})
    assert hash_of(Point(0, 1)) != hash_of(Point(1, 0))


def test_pydantic_model_extra_fields_are_rejected():
    class Extra(BaseModel):
        model_config = ConfigDict(frozen=True, extra="allow")
        a: int

    with pytest.raises(UnsupportedTypeError, match="extra"):
        freeze(Extra(a=1, b=2))
