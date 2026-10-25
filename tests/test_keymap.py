"""Key map behavior from specs/dimensions/spec.md."""

import random

import pytest

from permafrost import keymap, registry
from permafrost.nodes import KMBranch, KMCollision


def vh(i: int) -> bytes:
    return i.to_bytes(16, "big")


def build(pairs):
    root = keymap.EMPTY
    for key, value in pairs:
        root = keymap.set(root, key, value)
    return root


@pytest.fixture(scope="module")
def big():
    return build((f"key-{i}", vh(i)) for i in range(10_000))


def test_insert_get_and_items():
    root = build((f"k{i}", vh(i)) for i in range(500))
    assert all(keymap.get(root, f"k{i}") == vh(i) for i in range(500))
    assert keymap.get(root, "missing") is None
    assert dict(keymap.items(root)) == {f"k{i}": vh(i) for i in range(500)}
    assert sorted(keymap.keys(root)) == sorted(f"k{i}" for i in range(500))


def test_set_same_value_returns_same_root():
    root = build([("a", vh(1))])
    assert keymap.set(root, "a", vh(1)) is root


def test_delete_missing_key_returns_same_root():
    root = build([("a", vh(1))])
    assert keymap.delete(root, "b") is root


def test_delete_everything_gives_the_empty_key_map():
    root = build((f"k{i}", vh(i)) for i in range(300))
    for i in range(300):
        root = keymap.delete(root, f"k{i}")
    assert root is keymap.EMPTY


def test_random_insert_and_delete_sequences_give_the_same_root():
    rng = random.Random(1234)
    final = {f"key-{i}": vh(i) for i in range(40)}
    expected = build(sorted(final.items()))._pf_hash
    for _ in range(1000):
        extra = [f"extra-{rng.randrange(100)}" for _ in range(rng.randrange(1, 20))]
        ops = [("set", k, v) for k, v in final.items()]
        ops += [("set", k, vh(999)) for k in extra]
        rng.shuffle(ops)
        # Delete each extra key at a random point after it was set.
        root = keymap.EMPTY
        pending_deletes = set()
        for op, key, value in ops:
            root = keymap.set(root, key, value)
            if key.startswith("extra-"):
                pending_deletes.add(key)
            if pending_deletes and rng.random() < 0.3:
                root = keymap.delete(root, pending_deletes.pop())
        for key in pending_deletes:
            root = keymap.delete(root, key)
        assert root._pf_hash == expected


def test_keys_with_equal_hashes_share_a_collision_node(monkeypatch):
    real = keymap.key_hash

    def fake(key):
        return 12345 if key.startswith("same-") else real(key)

    monkeypatch.setattr(keymap, "key_hash", fake)
    root = build([("same-a", vh(1)), ("same-b", vh(2)), ("other", vh(3))])
    assert keymap.get(root, "same-a") == vh(1)
    assert keymap.get(root, "same-b") == vh(2)
    assert any(type(n) is KMCollision for n in keymap.nodes(root))

    root2 = build([("other", vh(3)), ("same-b", vh(2)), ("same-a", vh(1))])
    assert root2 is root

    root = keymap.set(root, "same-c", vh(4))
    root = keymap.set(root, "same-c", vh(5))
    assert keymap.get(root, "same-c") == vh(5)
    root = keymap.delete(root, "same-c")
    root = keymap.delete(root, "same-a")
    assert root is build([("same-b", vh(2)), ("other", vh(3))])
    assert not any(type(n) is KMCollision for n in keymap.nodes(root))


def test_keys_that_share_a_long_prefix(monkeypatch):
    real = keymap.key_hash
    # Equal on the first 60 bits, different after.
    monkeypatch.setattr(
        keymap,
        "key_hash",
        lambda k: (1 << 100) | (1 << 3) if k == "x" else (1 << 100) | (1 << 7) if k == "y" else real(k),
    )
    root = build([("x", vh(1)), ("y", vh(2))])
    assert keymap.get(root, "x") == vh(1) and keymap.get(root, "y") == vh(2)
    assert keymap.delete(keymap.delete(root, "x"), "y") is keymap.EMPTY


def test_diff_of_two_key_maps():
    a = build([("a", vh(1)), ("b", vh(2)), ("c", vh(3))])
    b = build([("a", vh(1)), ("b", vh(9)), ("d", vh(4))])
    assert sorted(keymap.diff(a, b)) == [("b", "changed"), ("c", "removed"), ("d", "added")]
    assert keymap.diff(a, a) == []


def test_diff_reads_only_the_path_to_the_changed_key(big, monkeypatch):
    changed = keymap.set(big, "key-77", vh(-1 & 0xFF))
    reads = []
    original = keymap._diff_nodes

    def counting(a, b, out):
        if type(a) is KMBranch and type(b) is KMBranch and a._pf_hash != b._pf_hash:
            reads.append(a)
        original(a, b, out)

    monkeypatch.setattr(keymap, "_diff_nodes", counting)
    assert keymap.diff(big, changed) == [("key-77", "changed")]
    assert 1 <= len(reads) <= 4


class _Counter:
    def __init__(self):
        self.created = []

    def node_created(self, h, node):
        self.created.append(node)


def test_change_one_key_among_10000(big):
    # Only the key map nodes on the path to the key are new. The length of the
    # path depends on how many other keys share a prefix of the key hash: about
    # log32(n) on average, and more for the few keys that share a long prefix.
    counter = _Counter()
    registry.add_listener(counter)
    counts = []
    try:
        for i in range(500):
            counter.created.clear()
            keymap.set(big, f"key-{i * 19}", vh(10_000_000 + i))
            counts.append(len([n for n in counter.created if type(n) in (KMBranch, KMCollision)]))
    finally:
        registry.remove_listener(counter)
    assert min(counts) >= 1
    assert sum(counts) / len(counts) <= 4
    assert max(counts) <= 7
