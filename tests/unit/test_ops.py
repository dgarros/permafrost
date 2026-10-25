"""Scenarios of specs/value-updates/spec.md."""

import pytest

from permafrost import FrozenList, PathError, delete_in, freeze, hash_of, merge, set_in

from ..models import Device, Interface, Site

# Paths inside a value


def test_path_through_a_dictionary_a_list_and_a_model():
    value = freeze({"devices": [Device(name="r1"), Device(name="r2")]})
    new = set_in(value, ("devices", 0, "name"), "core-1")
    assert new["devices"][0].name == "core-1"
    assert new["devices"][1] is value["devices"][1]
    assert value["devices"][0].name == "r1"


def test_path_to_a_missing_list_index():
    with pytest.raises(PathError):
        set_in({"devices": [1, 2]}, ("devices", 5), 3)


def test_path_with_a_missing_intermediate_key():
    with pytest.raises(PathError):
        set_in({"a": {}}, ("a", "b", "c"), 1)


def test_path_into_a_scalar():
    with pytest.raises(PathError):
        set_in({"a": 1}, ("a", "b"), 1)


# Set


def test_replace_a_nested_value():
    before = freeze({"a": {"b": 1}})
    after = set_in(before, ("a", "b"), 2)
    assert after == {"a": {"b": 2}}
    assert before == {"a": {"b": 1}}


def test_add_a_dictionary_key():
    assert set_in({"a": {"b": 1}}, ("a", "c"), 3) == {"a": {"b": 1, "c": 3}}


def test_set_a_field_that_the_model_does_not_have():
    with pytest.raises(PathError):
        set_in(Device(name="r1"), ("vendor",), "x")


def test_set_with_an_empty_path():
    before = freeze({"a": 1})
    with pytest.raises(PathError, match="freeze"):
        set_in(before, (), [1])
    assert before == {"a": 1}


def test_set_an_item_of_a_tuple_field():
    d = Device(name="r1", interfaces=(Interface(name="e0"), Interface(name="e1")))
    new = set_in(d, ("interfaces", 1, "vlans"), (5,))
    assert new.interfaces[1].vlans == (5,)
    assert new.interfaces[0] is freeze(d).interfaces[0]


# Delete


def test_delete_a_dictionary_key():
    assert delete_in({"a": {"b": 1, "c": 2}}, ("a", "b")) == {"a": {"c": 2}}


def test_delete_a_list_item():
    assert delete_in([10, 20, 30], (1,)) == [10, 30]


def test_delete_a_model_field():
    with pytest.raises(PathError):
        delete_in(Device(name="r1"), ("site",))


def test_delete_a_missing_key():
    with pytest.raises(PathError):
        delete_in({"a": 1}, ("b",))


# Merge


def test_merge_nested_dictionaries():
    assert merge({"a": {"b": 1}, "d": 4}, {"a": {"c": 3}}) == {"a": {"b": 1, "c": 3}, "d": 4}


def test_merge_into_a_model():
    new = merge(Device(name="r1", site="paris"), {"name": "r2"})
    assert type(new) is Device and new.name == "r2" and new.site == "paris"


def test_merge_into_a_pydantic_model():
    new = merge(Site(name="paris", devices=["r1"]), {"devices": ["r2"]}, lists="append")
    assert type(new) is Site and new.devices == ["r1", "r2"]


def test_merge_a_model_into_a_model():
    new = merge({"d": Device(name="r1", site="lyon")}, {"d": Device(name="r2")})
    assert new["d"] == Device(name="r2", site="paris")


def test_merge_an_unknown_model_field():
    with pytest.raises(PathError):
        merge(Device(name="r1"), {"vendor": "x"})


def test_merge_a_scalar_over_a_dictionary():
    assert merge({"a": {"b": 1}}, {"a": 5}) == {"a": 5}


def test_merge_lists_with_replace():
    assert merge({"tags": ["a"]}, {"tags": ["b"]}, lists="replace") == {"tags": ["b"]}
    assert merge({"tags": ["a"]}, {"tags": ["b"]}) == {"tags": ["b"]}


def test_merge_lists_with_append():
    result = merge({"tags": ["a"]}, {"tags": ["b"]}, lists="append")
    assert result == {"tags": ["a", "b"]}
    assert isinstance(result["tags"], FrozenList)


def test_merge_with_an_unknown_list_behavior():
    with pytest.raises(ValueError):
        merge({}, {}, lists="incremental")  # ty: ignore[no-matching-overload]


# Sharing


def test_change_one_leaf_of_a_large_value():
    before = freeze({"left": {"deep": {"x": 1}}, "right": {"big": list(range(100))}})
    after = set_in(before, ("left", "deep", "x"), 2)
    assert after["right"] is before["right"]
    merged = merge(before, {"left": {"deep": {"y": 1}}})
    assert merged["right"] is before["right"]


def test_set_a_value_to_its_current_content():
    before = freeze({"a": 1, "b": [1]})
    assert hash_of(set_in(before, ("a",), 1)) == hash_of(before)
    assert set_in(before, ("b",), [1]) is before
    assert merge(before, {"b": [1]}) is before
