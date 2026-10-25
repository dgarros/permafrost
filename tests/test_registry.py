from permafrost import freeze, hash_of, registry


def test_node_leaves_registry_when_freed(collect):
    node = freeze({"only-here": [1, 2, 3]})
    h = hash_of(node)
    assert registry.lookup(h) is node
    del node
    collect()
    assert registry.lookup(h) is None
