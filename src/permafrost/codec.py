"""Deterministic msgpack encoding of nodes, and their hash.

Each node is encoded as a msgpack array ``[tag, ...payload]``. A child node is
written as a msgpack extension holding its 16-byte hash. The same bytes give
the hash of the node and are what the external cache stores.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Iterable
from datetime import date, datetime
from enum import Enum

import msgpack

from .nodes import KMChild

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
EXT_ENUM = 5

HASH_SIZE = 16

_INT_MIN = -(2**63)
_INT_MAX = 2**64 - 1

# Values stored inside their parent node, or on their own as the root of a value.
type Scalar = str | int | float | bool | bytes | date | datetime | None

SCALAR_TYPES: frozenset[type] = frozenset({type(None), bool, int, float, str, bytes, date, datetime})

# Name written in the encoding of each member, by enum class, or None for a
# class whose members are not scalars. Filled the first time a class is seen.
_enum_names: dict[type, str | None] = {}


def enum_name(t: type) -> str | None:
    """Return the name of ``t`` in the encoding when its members are scalars, or ``None``.

    The members of an enum class that subclasses ``str`` or ``int`` are scalars,
    named ``module:qualname`` unless the class was registered under another name.
    """
    try:
        return _enum_names[t]
    except KeyError:
        pass
    name = None
    if issubclass(t, Enum) and issubclass(t, (str, int)):
        name = f"{t.__module__}:{t.__qualname__}"
    _enum_names[t] = name
    return name


def is_enum_scalar_type(t: type) -> bool:
    """Return whether ``t`` is an enum class whose members are scalars."""
    return enum_name(t) is not None


def is_scalar_type(t: type) -> bool:
    """Return whether values of type ``t`` are scalars: a built-in scalar type or an enum class of scalars."""
    return t in SCALAR_TYPES or enum_name(t) is not None


def register_enum(t: type, name: str) -> None:
    """Write the members of the enum class ``t`` under ``name`` in the encoding."""
    _enum_names[t] = name


def exclude_enum(t: type) -> None:
    """Stop treating the members of ``t`` as scalars, because a type handler stores them."""
    _enum_names[t] = None


class Ref:
    """A child node in decoded content, identified by its hash."""

    __slots__ = ("hash",)

    def __init__(self, h: bytes) -> None:
        """Reference the child node with hash ``h``."""
        self.hash = h

    def __repr__(self) -> str:
        """Return ``Ref(<hex hash>)``."""
        return f"Ref({self.hash.hex()})"


class EnumValue:
    """An enum member in decoded content: the name of its class and its value."""

    __slots__ = ("name", "value")

    def __init__(self, name: str, value: object) -> None:
        """Hold the member with value ``value`` of the enum class named ``name``."""
        self.name = name
        self.value = value

    def __repr__(self) -> str:
        """Return ``EnumValue(<name>, <value>)``."""
        return f"EnumValue({self.name!r}, {self.value!r})"


# What the encoder passes to msgpack: scalars, extension values and nested arrays.
type Packable = Scalar | msgpack.ExtType | list[Packable]

# Returns the hash of a child node.
type HashOfNode = Callable[[object], bytes]


def digest(data: bytes) -> bytes:
    """Return the 16-byte BLAKE2b hash of encoded node bytes."""
    return hashlib.blake2b(data, digest_size=HASH_SIZE).digest()


def _pack(obj: Packable) -> bytes:
    """Encode ``obj`` with msgpack, writing ``bytes`` as msgpack binary."""
    return msgpack.packb(obj, use_bin_type=True)


def _no_children(item: object) -> bytes:
    """Raise ``TypeError``: the root of a scalar value has no child node to hash."""
    raise TypeError(f"a scalar root has no child node, found {type(item).__qualname__}")


def encode_item(item: object, hash_of_node: HashOfNode) -> Packable:
    """Return the msgpack form of a scalar or of a reference to a child node."""
    if type(item) is int:
        if _INT_MIN <= item <= _INT_MAX:
            return item
        return msgpack.ExtType(EXT_BIGINT, str(item).encode())
    if item is None or type(item) is str or type(item) is float or type(item) is bool or type(item) is bytes:
        return item
    if type(item) is datetime:
        return msgpack.ExtType(EXT_DATETIME, item.isoformat().encode())
    if type(item) is date:
        return msgpack.ExtType(EXT_DATE, item.isoformat().encode())
    name = enum_name(type(item))
    if name is not None and isinstance(item, Enum):
        return msgpack.ExtType(EXT_ENUM, _pack([name, encode_item(item.value, _no_children)]))
    return msgpack.ExtType(EXT_REF, hash_of_node(item))


def encode_scalar_root(value: Scalar) -> bytes:
    """Encode a scalar that is the whole value, as a node of its own."""
    return _pack([TAG_SCALAR, encode_item(value, _no_children)])


def encode_mapping(tag: int, pairs: Iterable[tuple[object, object]], hash_of_node: HashOfNode) -> bytes:
    """Encode dictionary entries, sorted by the encoded bytes of the key."""
    entries: list[tuple[bytes, Packable, Packable]] = []
    for k, v in pairs:
        ek = encode_item(k, hash_of_node)
        entries.append((_pack(ek), ek, encode_item(v, hash_of_node)))
    entries.sort(key=lambda e: e[0])
    return _pack([tag, [[ek, ev] for _, ek, ev in entries]])


def encode_sequence(tag: int, items: Iterable[object], hash_of_node: HashOfNode) -> bytes:
    """Encode the items of a list or tuple node, in order, under ``tag``."""
    return _pack([tag, [encode_item(i, hash_of_node) for i in items]])


def encode_set(items: Iterable[object], hash_of_node: HashOfNode) -> bytes:
    """Encode the items of a set node, sorted by their encoded bytes so the same set always gives the same bytes."""
    encoded = [encode_item(i, hash_of_node) for i in items]
    encoded.sort(key=_pack)
    return _pack([TAG_SET, encoded])


def encode_model(tag: int, path: str, values: Iterable[object], hash_of_node: HashOfNode) -> bytes:
    """Encode a dataclass or Pydantic model node: its class path and its field values in field order."""
    return _pack([tag, path, [encode_item(v, hash_of_node) for v in values]])


def encode_handler(name: str, inner: object, hash_of_node: HashOfNode) -> bytes:
    """Encode a value converted by the type handler named ``name``, from its converted form ``inner``."""
    return _pack([TAG_HANDLER, name, encode_item(inner, hash_of_node)])


def encode_km_branch(bitmap: int, children: Iterable[KMChild], hash_of_node: HashOfNode) -> bytes:
    """Encode a key map branch: its bitmap of used slots and its children.

    An entry child is written as ``[key, value_hash]`` and a branch or collision child as a reference to its hash.
    """
    out: list[Packable] = []
    for child in children:
        if isinstance(child, tuple):
            out.append([child[0], child[1]])
        else:
            out.append(msgpack.ExtType(EXT_REF, hash_of_node(child)))
    return _pack([TAG_KM_BRANCH, bitmap, out])


def encode_km_collision(entries: Iterable[tuple[str, bytes]]) -> bytes:
    """Encode a key map collision node from its ``(key, value_hash)`` entries."""
    return _pack([TAG_KM_COLLISION, [[k, v] for k, v in entries]])


def _ext_hook(code: int, data: bytes) -> object:
    """Decode a msgpack extension value: a child reference, a date, a datetime, a large integer or an enum member."""
    if code == EXT_REF:
        return Ref(data)
    if code == EXT_DATETIME:
        return datetime.fromisoformat(data.decode())
    if code == EXT_DATE:
        return date.fromisoformat(data.decode())
    if code == EXT_BIGINT:
        return int(data.decode())
    if code == EXT_ENUM:
        content = msgpack.unpackb(data, raw=False, ext_hook=_ext_hook)
        if type(content) is not list or len(content) != 2 or type(content[0]) is not str:
            raise ValueError("the data is not the encoding of an enum member")
        return EnumValue(content[0], content[1])
    return msgpack.ExtType(code, data)


def unpack(data: bytes) -> list[object]:
    """Decode the bytes of a node into its tag and payload, with ``Ref`` for each child.

    Raises ``ValueError`` when the bytes are not the encoding of a node.
    """
    payload = msgpack.unpackb(data, raw=False, ext_hook=_ext_hook, strict_map_key=False)
    if type(payload) is not list or not payload or type(payload[0]) is not int:
        raise ValueError("the data is not the encoding of a node")
    return payload


def refs_in(payload: object) -> list[bytes]:
    """Return the hashes of the child nodes referenced by a decoded node."""
    out: list[bytes] = []
    stack: list[object] = [payload]
    while stack:
        item = stack.pop()
        if type(item) is Ref:
            out.append(item.hash)
        elif type(item) is list:
            stack.extend(item)
    return out
