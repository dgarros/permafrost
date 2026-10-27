"""Scenarios of specs/value-diff/spec.md, except the dimension scenario (see test_store.py)."""

import importlib

from permafrost import DiffEntry, diff, equal, freeze, set_in

# permafrost.diff is the function, so get the module from importlib.
diff_module = importlib.import_module("permafrost.diff")

from ..models import Device, Interface, Item, State


def test_two_equal_values_built_separately():
    assert equal({"a": [1, {"b": 2}]}, {"a": [1, {"b": 2}]})


def test_changed_nested_key():
    assert diff({"a": {"b": 1}}, {"a": {"b": 2}}) == [DiffEntry(("a", "b"), "changed", 1, 2)]


def test_added_and_removed_keys():
    entries = diff({"a": 1}, {"b": 2})
    assert DiffEntry(("a",), "removed", 1, None) in entries
    assert DiffEntry(("b",), "added", None, 2) in entries
    assert len(entries) == 2


def test_equal_values():
    assert diff({"a": [1, 2]}, {"a": [1, 2]}) == []


def test_list_with_an_extra_item():
    assert diff([1, 2], [1, 2, 3]) == [DiffEntry((2,), "added", None, 3)]
    assert diff([1, 2, 3], [1, 2]) == [DiffEntry((2,), "removed", 3, None)]


def test_different_types_at_the_same_path():
    entries = diff({"a": [1]}, {"a": {"x": 1}})
    assert len(entries) == 1 and entries[0].path == ("a",) and entries[0].kind == "changed"


def test_list_and_tuple_with_the_same_items():
    assert [e.kind for e in diff({"a": [1]}, {"a": (1,)})] == ["changed"]


def test_scalars_of_different_types():
    assert diff({"a": 1}, {"a": True}) == [DiffEntry(("a",), "changed", 1, True)]


def test_sets():
    entries = diff({"tags": {"a", "b"}}, {"tags": {"b", "c"}})
    assert DiffEntry(("tags", "a"), "removed", "a", None) in entries
    assert DiffEntry(("tags", "c"), "added", None, "c") in entries
    assert len(entries) == 2


def test_models_field_by_field():
    a = Device(name="r1", interfaces=(Interface(name="e0", vlans=(1,)),))
    b = Device(name="r1", interfaces=(Interface(name="e0", vlans=(1, 2)),))
    assert diff(a, b) == [DiffEntry(("interfaces", 0, "vlans", 1), "added", None, 2)]


def test_models_of_different_classes():
    entries = diff({"x": Device(name="r1")}, {"x": Interface(name="r1")})
    assert [(e.path, e.kind) for e in entries] == [(("x",), "changed")]


def test_one_change_in_a_large_value(monkeypatch):
    before = freeze({f"subtree-{i}": {"items": list(range(20)), "id": i} for i in range(1000)})
    after = set_in(before, ("subtree-500", "items", 3), -1)

    calls = []
    original = diff_module._diff

    def counting(a, b, path, out):
        calls.append(path)
        original(a, b, path, out)

    monkeypatch.setattr(diff_module, "_diff", counting)
    assert diff(before, after) == [DiffEntry(("subtree-500", "items", 3), "changed", 3, -1)]
    # The root, then one call for each of the 1,000 subtrees (999 return at once
    # because the hashes are equal), then the changed subtree's 2 fields, then
    # the 20 items of the changed list. No call goes inside an unchanged subtree.
    inside_unchanged = [p for p in calls if len(p) > 1 and p[0] != "subtree-500"]
    assert inside_unchanged == []
    assert len(calls) == 1 + 1000 + 2 + 20


def test_changed_enum_member_in_a_model_field():
    a = Item(name="a", state=State.PRESENT)
    b = Item(name="a", state=State.ABSENT)
    assert diff(a, b) == [DiffEntry(("state",), "changed", State.PRESENT, State.ABSENT)]


def test_enum_member_replaced_by_its_plain_value():
    entries = diff({"s": State.PRESENT}, {"s": "present"})
    assert entries == [DiffEntry(("s",), "changed", State.PRESENT, "present")]
    assert type(entries[0].old) is State and type(entries[0].new) is str
