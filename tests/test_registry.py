import pytest

from permafrost import FrozenDict, FrozenList, freeze, hash_of, registry


def test_node_leaves_registry_when_freed(collect):
    node = freeze({"only-here": [1, 2, 3]})
    h = hash_of(node)
    assert registry.lookup(h, object) is node
    del node
    collect()
    assert registry.lookup(h, object) is None


def test_lookup_checks_the_class():
    node = freeze({"checked": 1})
    h = hash_of(node)
    assert registry.lookup(h, FrozenDict) is node
    with pytest.raises(TypeError, match="not a FrozenList"):
        registry.lookup(h, FrozenList)
