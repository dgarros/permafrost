"""Key map: a hash array mapped trie from key to the hash of a value root.

Each key is placed by successive 5-bit groups of the BLAKE2b hash of the key.
A branch has up to 32 children. A child is either an entry ``(key,
value_hash)`` or another branch. The shape is canonical: a branch below the
root exists only when at least two keys share its prefix, so the same set of
entries always gives the same tree and the same root hash.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterator
from typing import Literal

from . import codec, registry
from .nodes import KMBranch, KMChild, KMCollision
from .types import node_hash

BITS = 5
# 25 levels use 125 of the 128 bits of the key hash. Keys whose hashes are
# equal on all of them share a collision node at the next level.
MAX_DEPTH = 25

Entry = tuple[str, bytes]
Kind = Literal["added", "removed", "changed"]


def key_hash(key: str) -> int:
    """Return the 128-bit BLAKE2b hash of ``key`` as an integer."""
    return int.from_bytes(hashlib.blake2b(key.encode(), digest_size=16).digest())


def _slot(kh: int, depth: int) -> int:
    """Return the slot, from 0 to 31, that the key with hash ``kh`` takes in a branch at ``depth``."""
    return (kh >> (128 - BITS * (depth + 1))) & 31


def make_branch(bitmap: int, children: tuple[KMChild, ...]) -> KMBranch:
    """Return the branch node with these slots and children, reusing a registered node with the same hash."""
    h = codec.digest(codec.encode_km_branch(bitmap, children, node_hash))
    node = registry.lookup(h, KMBranch)
    if node is not None:
        return node
    return registry.add(h, KMBranch._new(bitmap, children, h))


def make_collision(entries: tuple[Entry, ...]) -> KMCollision:
    """Return the collision node with these entries sorted by key, reusing a registered node with the same hash."""
    entries = tuple(sorted(entries))
    h = codec.digest(codec.encode_km_collision(entries))
    node = registry.lookup(h, KMCollision)
    if node is not None:
        return node
    return registry.add(h, KMCollision._new(entries, h))


def empty() -> KMBranch:
    """Return the key map that holds no key."""
    return make_branch(0, ())


# The empty key map stays in memory, so every store and dimension shares it.
EMPTY = empty()


def get(root: KMBranch, key: str) -> bytes | None:
    """Return the value hash stored under ``key``, or ``None``."""
    kh = key_hash(key)
    node: KMBranch | KMCollision = root
    depth = 0
    while True:
        if type(node) is KMCollision:
            for k, v in node.entries:
                if k == key:
                    return v
            return None
        bit = 1 << _slot(kh, depth)
        if not node.bitmap & bit:
            return None
        child = node.children[(node.bitmap & (bit - 1)).bit_count()]
        if isinstance(child, tuple):
            return child[1] if child[0] == key else None
        node = child
        depth += 1


def set(root: KMBranch, key: str, value_hash: bytes) -> KMBranch:
    """Return a key map with ``key`` set to ``value_hash``."""
    result = _set(root, key, key_hash(key), value_hash, 0)
    assert type(result) is KMBranch
    return result


def _set(node: KMBranch | KMCollision, key: str, kh: int, vh: bytes, depth: int) -> KMBranch | KMCollision:
    """Return ``node`` with ``key`` set to value hash ``vh``, or ``node`` itself when nothing changes."""
    if type(node) is KMCollision:
        entries = dict(node.entries)
        if entries.get(key) == vh:
            return node
        entries[key] = vh
        return make_collision(tuple(entries.items()))
    bit = 1 << _slot(kh, depth)
    idx = (node.bitmap & (bit - 1)).bit_count()
    kids = node.children
    if not node.bitmap & bit:
        return make_branch(node.bitmap | bit, kids[:idx] + ((key, vh),) + kids[idx:])
    child = kids[idx]
    new_child: KMChild
    if isinstance(child, tuple):
        if child[0] == key:
            if child[1] == vh:
                return node
            new_child = (key, vh)
        else:
            new_child = _pair(child, key_hash(child[0]), (key, vh), kh, depth + 1)
    else:
        new_child = _set(child, key, kh, vh, depth + 1)
        if new_child is child:
            return node
    return make_branch(node.bitmap, kids[:idx] + (new_child,) + kids[idx + 1 :])


def _pair(e1: Entry, kh1: int, e2: Entry, kh2: int, depth: int) -> KMBranch | KMCollision:
    """Return the node that holds two entries whose keys share the prefix up to ``depth``."""
    if depth >= MAX_DEPTH:
        return make_collision((e1, e2))
    s1, s2 = _slot(kh1, depth), _slot(kh2, depth)
    if s1 == s2:
        return make_branch(1 << s1, (_pair(e1, kh1, e2, kh2, depth + 1),))
    if s1 > s2:
        e1, e2 = e2, e1
    return make_branch((1 << s1) | (1 << s2), (e1, e2))


def delete(root: KMBranch, key: str) -> KMBranch:
    """Return a key map without ``key``. Returns ``root`` when the key is absent."""
    result = _delete(root, key, key_hash(key), 0)
    assert type(result) is KMBranch
    return result


def _delete(node: KMBranch | KMCollision, key: str, kh: int, depth: int) -> KMChild | None:
    """Return the new node, an entry when only one entry is left below depth 0, or ``None``."""
    if type(node) is KMCollision:
        entries = tuple(e for e in node.entries if e[0] != key)
        if len(entries) == len(node.entries):
            return node
        if len(entries) == 1:
            return entries[0]
        return make_collision(entries)
    bit = 1 << _slot(kh, depth)
    if not node.bitmap & bit:
        return node
    idx = (node.bitmap & (bit - 1)).bit_count()
    kids = node.children
    child = kids[idx]
    new_child: KMChild | None
    if isinstance(child, tuple):
        if child[0] != key:
            return node
        new_child = None
    else:
        new_child = _delete(child, key, kh, depth + 1)
        if new_child is child:
            return node
    if new_child is None:
        bitmap = node.bitmap & ~bit
        kids = kids[:idx] + kids[idx + 1 :]
    else:
        bitmap = node.bitmap
        kids = kids[:idx] + (new_child,) + kids[idx + 1 :]
    if depth > 0 and len(kids) == 1 and type(kids[0]) is tuple:
        return kids[0]
    return make_branch(bitmap, kids)


def items(root: KMChild) -> Iterator[Entry]:
    """Yield each ``(key, value_hash)`` entry, in no defined order."""
    stack: list[KMChild] = [root]
    while stack:
        node = stack.pop()
        if isinstance(node, tuple):
            yield node
        elif type(node) is KMCollision:
            yield from node.entries
        else:
            stack.extend(node.children)


def keys(root: KMBranch) -> Iterator[str]:
    """Yield each key, in no defined order."""
    for key, _ in items(root):
        yield key


def nodes(root: KMBranch) -> Iterator[KMBranch | KMCollision]:
    """Yield each key map node of the tree."""
    stack: list[KMBranch | KMCollision] = [root]
    while stack:
        node = stack.pop()
        yield node
        if type(node) is KMBranch:
            stack.extend(c for c in node.children if not isinstance(c, tuple))


def diff(a: KMBranch, b: KMBranch) -> list[tuple[str, Kind]]:
    """Return the keys whose value hashes differ between two key maps.

    Subtrees with the same hash on both sides are skipped.
    """
    out: list[tuple[str, Kind]] = []
    _diff_nodes(a, b, out)
    return out


def _diff_nodes(a: KMChild | None, b: KMChild | None, out: list[tuple[str, Kind]]) -> None:
    """Append to ``out`` each key whose value hash differs between the subtrees ``a`` and ``b``.

    ``None`` stands for an empty slot. Branches are compared slot by slot; any other pair is compared entry by entry.
    """
    if a is b:
        return
    if type(a) is KMBranch and type(b) is KMBranch:
        if a._pf_hash == b._pf_hash:
            return
        bitmap = a.bitmap | b.bitmap
        while bitmap:
            bit = bitmap & -bitmap
            bitmap ^= bit
            _diff_nodes(_child(a, bit), _child(b, bit), out)
        return
    if type(a) is tuple and type(b) is tuple and a == b:
        return
    if type(a) is KMCollision and type(b) is KMCollision and a._pf_hash == b._pf_hash:
        return
    left = dict(_entries(a))
    right = dict(_entries(b))
    for key, vh in left.items():
        other = right.get(key)
        if other is None:
            out.append((key, "removed"))
        elif other != vh:
            out.append((key, "changed"))
    for key in right.keys() - left.keys():
        out.append((key, "added"))


def _child(node: KMBranch, bit: int) -> KMChild | None:
    """Return the child in the slot of ``bit``, or ``None`` when the slot is empty."""
    if not node.bitmap & bit:
        return None
    return node.children[(node.bitmap & (bit - 1)).bit_count()]


def _entries(node: KMChild | None) -> Iterator[Entry]:
    """Yield each entry below ``node``, or none when ``node`` is ``None``."""
    if node is None:
        return iter(())
    return items(node)
