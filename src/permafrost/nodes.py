"""Read-only node classes.

Every node stores its content hash in the ``_pf_hash`` slot. Nodes are created
only by Permafrost (``permafrost.types`` and ``permafrost.keymap``), which sets
the slots through the member descriptors and so bypasses ``__setattr__``.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence, Set
from typing import Any, NoReturn

from .errors import ReadOnlyError


def _read_only(self: object, *args: Any) -> NoReturn:
    raise ReadOnlyError(f"{type(self).__name__} is read-only")


class _Frozen:
    __slots__ = ()

    __setattr__ = _read_only
    __delattr__ = _read_only

    def __hash__(self) -> int:
        return int.from_bytes(self._pf_hash[:8])  # type: ignore[attr-defined]

    def __copy__(self) -> Any:
        return self

    def __deepcopy__(self, memo: Any) -> Any:
        return self

    def __reduce__(self) -> NoReturn:
        raise TypeError(f"{type(self).__name__} cannot be pickled")


class FrozenDict(_Frozen, Mapping[Any, Any]):
    """Read-only dictionary."""

    __slots__ = ("_data", "_pf_hash", "__weakref__")

    _data: dict[Any, Any]
    _pf_hash: bytes

    @classmethod
    def _new(cls, data: dict[Any, Any], h: bytes) -> FrozenDict:
        obj = object.__new__(cls)
        _set_dict_data(obj, data)
        _set_dict_hash(obj, h)
        return obj

    def __getitem__(self, key: Any) -> Any:
        return self._data[key]

    def __iter__(self) -> Iterator[Any]:
        return iter(self._data)

    def __len__(self) -> int:
        return len(self._data)

    def __contains__(self, key: object) -> bool:
        return key in self._data

    def keys(self):  # type: ignore[override]
        return self._data.keys()

    def values(self):  # type: ignore[override]
        return self._data.values()

    def items(self):  # type: ignore[override]
        return self._data.items()

    def get(self, key: Any, default: Any = None) -> Any:
        return self._data.get(key, default)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, FrozenDict):
            return self._pf_hash == other._pf_hash
        if isinstance(other, Mapping):
            return self._data == (other if isinstance(other, dict) else dict(other.items()))
        return NotImplemented

    __hash__ = _Frozen.__hash__

    def __or__(self, other: object) -> NoReturn:
        raise ReadOnlyError("FrozenDict is read-only, use permafrost.merge()")

    def __repr__(self) -> str:
        return f"FrozenDict({self._data!r})"


class _FrozenSequence(_Frozen, Sequence[Any]):
    __slots__ = ()

    _data: tuple[Any, ...]

    def __getitem__(self, index: Any) -> Any:
        return self._data[index]

    def __iter__(self) -> Iterator[Any]:
        return iter(self._data)

    def __len__(self) -> int:
        return len(self._data)

    def __contains__(self, item: object) -> bool:
        return item in self._data

    def __reversed__(self) -> Iterator[Any]:
        return reversed(self._data)

    def __repr__(self) -> str:
        return f"{type(self).__name__}({list(self._data)!r})"


class FrozenList(_FrozenSequence):
    """Read-only list."""

    __slots__ = ("_data", "_pf_hash", "__weakref__")

    _pf_hash: bytes

    @classmethod
    def _new(cls, items: tuple[Any, ...], h: bytes) -> FrozenList:
        obj = object.__new__(cls)
        _set_list_data(obj, items)
        _set_list_hash(obj, h)
        return obj

    def __eq__(self, other: object) -> bool:
        if isinstance(other, FrozenList):
            return self._pf_hash == other._pf_hash
        if isinstance(other, list):
            return len(self._data) == len(other) and all(a == b for a, b in zip(self._data, other))
        return NotImplemented

    __hash__ = _Frozen.__hash__


class FrozenTuple(_FrozenSequence):
    """Read-only tuple."""

    __slots__ = ("_data", "_pf_hash", "__weakref__")

    _pf_hash: bytes

    @classmethod
    def _new(cls, items: tuple[Any, ...], h: bytes) -> FrozenTuple:
        obj = object.__new__(cls)
        _set_tuple_data(obj, items)
        _set_tuple_hash(obj, h)
        return obj

    def __eq__(self, other: object) -> bool:
        if isinstance(other, FrozenTuple):
            return self._pf_hash == other._pf_hash
        if isinstance(other, tuple):
            return self._data == other
        return NotImplemented

    def __hash__(self) -> int:
        # Same hash as the built-in tuple, so that a FrozenTuple key matches a tuple key.
        return hash(self._data)


class FrozenSet(_Frozen, Set[Any]):
    """Read-only set."""

    __slots__ = ("_data", "_pf_hash", "__weakref__")

    _data: frozenset[Any]
    _pf_hash: bytes

    @classmethod
    def _new(cls, items: frozenset[Any], h: bytes) -> FrozenSet:
        obj = object.__new__(cls)
        _set_set_data(obj, items)
        _set_set_hash(obj, h)
        return obj

    @classmethod
    def _from_iterable(cls, it: Any) -> frozenset[Any]:
        return frozenset(it)

    def __iter__(self) -> Iterator[Any]:
        return iter(self._data)

    def __len__(self) -> int:
        return len(self._data)

    def __contains__(self, item: object) -> bool:
        return item in self._data

    def __eq__(self, other: object) -> bool:
        if isinstance(other, FrozenSet):
            return self._pf_hash == other._pf_hash
        if isinstance(other, (set, frozenset)):
            return self._data == other
        return NotImplemented

    def __hash__(self) -> int:
        # Same hash as the built-in frozenset.
        return hash(self._data)

    def __repr__(self) -> str:
        return f"FrozenSet({set(self._data)!r})"


class FrozenModel:
    """Base class for Pydantic dataclasses stored in Permafrost.

    It adds a slot for weak references and a slot for the content hash. Use it
    with ``@pydantic.dataclasses.dataclass(frozen=True, slots=True)``.
    """

    __slots__ = ("__weakref__", "_pf_hash")


class KMBranch(_Frozen):
    """Branch of a key map: a 32-bit bitmap and one child for each set bit.

    A child is either an entry ``(key, value_hash)`` or another key map node.
    """

    __slots__ = ("bitmap", "children", "_pf_hash", "__weakref__")

    bitmap: int
    children: tuple[Any, ...]
    _pf_hash: bytes

    @classmethod
    def _new(cls, bitmap: int, children: tuple[Any, ...], h: bytes) -> KMBranch:
        obj = object.__new__(cls)
        _set_branch_bitmap(obj, bitmap)
        _set_branch_children(obj, children)
        _set_branch_hash(obj, h)
        return obj

    def __eq__(self, other: object) -> bool:
        if isinstance(other, KMBranch):
            return self._pf_hash == other._pf_hash
        return NotImplemented

    __hash__ = _Frozen.__hash__

    def __repr__(self) -> str:
        return f"KMBranch({self._pf_hash.hex()})"


class KMCollision(_Frozen):
    """Key map node for keys whose key hashes are equal, sorted by key."""

    __slots__ = ("entries", "_pf_hash", "__weakref__")

    entries: tuple[tuple[str, bytes], ...]
    _pf_hash: bytes

    @classmethod
    def _new(cls, entries: tuple[tuple[str, bytes], ...], h: bytes) -> KMCollision:
        obj = object.__new__(cls)
        _set_collision_entries(obj, entries)
        _set_collision_hash(obj, h)
        return obj

    def __eq__(self, other: object) -> bool:
        if isinstance(other, KMCollision):
            return self._pf_hash == other._pf_hash
        return NotImplemented

    __hash__ = _Frozen.__hash__

    def __repr__(self) -> str:
        return f"KMCollision({self._pf_hash.hex()})"


_set_dict_data = FrozenDict.__dict__["_data"].__set__
_set_dict_hash = FrozenDict.__dict__["_pf_hash"].__set__
_set_list_data = FrozenList.__dict__["_data"].__set__
_set_list_hash = FrozenList.__dict__["_pf_hash"].__set__
_set_tuple_data = FrozenTuple.__dict__["_data"].__set__
_set_tuple_hash = FrozenTuple.__dict__["_pf_hash"].__set__
_set_set_data = FrozenSet.__dict__["_data"].__set__
_set_set_hash = FrozenSet.__dict__["_pf_hash"].__set__
_set_branch_bitmap = KMBranch.__dict__["bitmap"].__set__
_set_branch_children = KMBranch.__dict__["children"].__set__
_set_branch_hash = KMBranch.__dict__["_pf_hash"].__set__
_set_collision_entries = KMCollision.__dict__["entries"].__set__
_set_collision_hash = KMCollision.__dict__["_pf_hash"].__set__
set_model_hash = FrozenModel.__dict__["_pf_hash"].__set__

COLLECTION_TYPES = (FrozenDict, FrozenList, FrozenTuple, FrozenSet)
KEYMAP_TYPES = (KMBranch, KMCollision)
