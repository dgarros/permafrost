"""Deterministic msgpack encoding of nodes, and their hash.

Each node is encoded as a msgpack array ``[tag, ...payload]``. A child node is
written as a msgpack extension holding its 16-byte hash. The same bytes give
the hash of the node and are what the external cache stores.
"""

from __future__ import annotations

import hashlib
from datetime import date, datetime
from typing import Any

import msgpack

# Node tags.
TAG_SCALAR = 0
TAG_DICT = 1
TAG_LIST = 2
TAG_TUPLE = 3
TAG_SET = 4
TAG_DATACLASS = 5
TAG_PYDANTIC_MODEL = 6
TAG_HANDLER = 7
TAG_KM_BRANCH = 8
TAG_KM_COLLISION = 9

# Extension type codes.
EXT_REF = 1
EXT_DATE = 2
EXT_DATETIME = 3
EXT_BIGINT = 4

HASH_SIZE = 16

_INT_MIN = -(2**63)
_INT_MAX = 2**64 - 1

SCALAR_TYPES: frozenset[type] = frozenset({type(None), bool, int, float, str, bytes, date, datetime})


class Ref:
    """A child node in decoded content, identified by its hash."""

    __slots__ = ("hash",)

    def __init__(self, h: bytes) -> None:
        self.hash = h

    def __repr__(self) -> str:
        return f"Ref({self.hash.hex()})"


def digest(data: bytes) -> bytes:
    return hashlib.blake2b(data, digest_size=HASH_SIZE).digest()


def _pack(obj: Any) -> bytes:
    return msgpack.packb(obj, use_bin_type=True)


def encode_item(item: Any, hash_of_node: Any) -> Any:
    """Return the msgpack form of a scalar or of a reference to a child node."""
    t = type(item)
    if t is int:
        if _INT_MIN <= item <= _INT_MAX:
            return item
        return msgpack.ExtType(EXT_BIGINT, str(item).encode())
    if t in (str, float, bool, bytes) or item is None:
        return item
    if t is datetime:
        return msgpack.ExtType(EXT_DATETIME, item.isoformat().encode())
    if t is date:
        return msgpack.ExtType(EXT_DATE, item.isoformat().encode())
    return msgpack.ExtType(EXT_REF, hash_of_node(item))


def encode_scalar_root(value: Any) -> bytes:
    return _pack([TAG_SCALAR, encode_item(value, None)])


def encode_mapping(tag: int, pairs: Any, hash_of_node: Any) -> bytes:
    """Encode dictionary entries, sorted by the encoded bytes of the key."""
    entries = []
    for k, v in pairs:
        ek = encode_item(k, hash_of_node)
        entries.append((_pack(ek), ek, encode_item(v, hash_of_node)))
    entries.sort(key=lambda e: e[0])
    return _pack([tag, [[ek, ev] for _, ek, ev in entries]])


def encode_sequence(tag: int, items: Any, hash_of_node: Any) -> bytes:
    return _pack([tag, [encode_item(i, hash_of_node) for i in items]])


def encode_set(items: Any, hash_of_node: Any) -> bytes:
    encoded = [encode_item(i, hash_of_node) for i in items]
    encoded.sort(key=_pack)
    return _pack([TAG_SET, encoded])


def encode_model(tag: int, path: str, values: Any, hash_of_node: Any) -> bytes:
    return _pack([tag, path, [encode_item(v, hash_of_node) for v in values]])


def encode_handler(name: str, inner: Any, hash_of_node: Any) -> bytes:
    return _pack([TAG_HANDLER, name, encode_item(inner, hash_of_node)])


def encode_km_branch(bitmap: int, children: Any, hash_of_node: Any) -> bytes:
    out = []
    for child in children:
        if type(child) is tuple:
            out.append([child[0], child[1]])
        else:
            out.append(msgpack.ExtType(EXT_REF, hash_of_node(child)))
    return _pack([TAG_KM_BRANCH, bitmap, out])


def encode_km_collision(entries: Any) -> bytes:
    return _pack([TAG_KM_COLLISION, [[k, v] for k, v in entries]])


def _ext_hook(code: int, data: bytes) -> Any:
    if code == EXT_REF:
        return Ref(data)
    if code == EXT_DATETIME:
        return datetime.fromisoformat(data.decode())
    if code == EXT_DATE:
        return date.fromisoformat(data.decode())
    if code == EXT_BIGINT:
        return int(data.decode())
    return msgpack.ExtType(code, data)


def unpack(data: bytes) -> list[Any]:
    """Decode the bytes of a node into its tag and payload, with ``Ref`` for each child."""
    return msgpack.unpackb(data, raw=False, ext_hook=_ext_hook, strict_map_key=False)


def refs_in(payload: Any) -> list[bytes]:
    """Return the hashes of the child nodes referenced by a decoded node."""
    out: list[bytes] = []
    stack = [payload]
    while stack:
        item = stack.pop()
        if type(item) is Ref:
            out.append(item.hash)
        elif type(item) is list:
            stack.extend(item)
    return out
