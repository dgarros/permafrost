import weakref

import pytest

from permafrost import FrozenDict, FrozenList, FrozenSet, FrozenTuple, ReadOnlyError, freeze

from .models import Device, Site


def test_dict_cannot_change():
    d = freeze({"a": 1})
    with pytest.raises(TypeError):
        d["b"] = 2  # type: ignore[index]
    with pytest.raises(TypeError):
        del d["a"]  # type: ignore[attr-defined]
    with pytest.raises(AttributeError):
        d.update({"b": 2})  # type: ignore[attr-defined]
    with pytest.raises(AttributeError):
        d.pop("a")  # type: ignore[attr-defined]
    with pytest.raises(ReadOnlyError):
        d._data = {}  # type: ignore[misc]
    with pytest.raises(ReadOnlyError):
        d |= {"b": 2}
    assert d == {"a": 1}


def test_list_cannot_change():
    lst = freeze([1, 2])
    for method, args in [
        ("append", (3,)),
        ("extend", ([3],)),
        ("insert", (0, 3)),
        ("pop", ()),
        ("remove", (1,)),
        ("sort", ()),
        ("clear", ()),
    ]:
        with pytest.raises(AttributeError):
            getattr(lst, method)(*args)
    with pytest.raises(TypeError):
        lst[0] = 5  # type: ignore[index]
    with pytest.raises(TypeError):
        del lst[0]  # type: ignore[attr-defined]
    with pytest.raises(ReadOnlyError):
        lst.foo = 1  # type: ignore[attr-defined]
    assert lst == [1, 2]


def test_set_cannot_change():
    s = freeze({1, 2})
    for method in ("add", "discard", "remove", "clear", "update"):
        with pytest.raises(AttributeError):
            getattr(s, method)(3)
    assert s == {1, 2}


def test_model_field_cannot_change():
    d = freeze(Device(name="r1"))
    with pytest.raises(Exception):
        d.name = "r2"  # type: ignore[misc]
    m = freeze(Site(name="s"))
    with pytest.raises(Exception):
        m.name = "t"  # type: ignore[misc]
    with pytest.raises(AttributeError):
        m.devices.append("x")
    assert d.name == "r1"


def test_read_operations_and_equality():
    d = freeze({"a": 1, "b": [1, 2], ("x", 1): "tuple key"})
    assert isinstance(d, FrozenDict)
    assert d["a"] == 1 and d.get("z") is None and "a" in d and len(d) == 3
    assert list(d) == ["a", "b", ("x", 1)]
    assert d[("x", 1)] == "tuple key"
    assert dict(d.items())["b"] == [1, 2]
    assert d == {"a": 1, "b": [1, 2], ("x", 1): "tuple key"}

    lst = freeze([1, 2, 3])
    assert isinstance(lst, FrozenList)
    assert lst == [1, 2, 3] and [1, 2, 3] == lst and lst != [1, 2]
    assert lst[0] == 1 and lst[-1] == 3 and lst[1:] == (2, 3)
    assert list(reversed(lst)) == [3, 2, 1] and lst.index(2) == 1 and lst.count(1) == 1 and 2 in lst

    t = freeze((1, 2))
    assert isinstance(t, FrozenTuple) and t == (1, 2) and hash(t) == hash((1, 2))
    assert lst != t

    s = freeze({1, 2})
    assert isinstance(s, FrozenSet) and s == {1, 2} and s == frozenset({1, 2})
    assert s & {2, 3} == {2} and s | {3} == {1, 2, 3} and s <= {1, 2, 3}


def test_nodes_support_weak_references():
    for value in ({"a": 1}, [1], (1,), {1}, Device(name="r1"), Site(name="s")):
        node = freeze(value)
        assert weakref.ref(node)() is node


def test_nodes_are_hashable():
    assert len({freeze({"a": 1}), freeze({"a": 1}), freeze([1]), freeze({1})}) == 3
