"""Diff between two values."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from .codec import SCALAR_TYPES
from .nodes import FrozenDict, FrozenList, FrozenSet, FrozenTuple
from .types import freeze, model_info_of, model_values, node_hash

Kind = Literal["added", "removed", "changed"]

ADDED: Kind = "added"
REMOVED: Kind = "removed"
CHANGED: Kind = "changed"


@dataclass(frozen=True, slots=True)
class DiffEntry:
    """One difference between two values.

    ``old`` is ``None`` for an added path and ``new`` is ``None`` for a removed path.
    """

    path: tuple[Any, ...]
    kind: Kind
    old: Any
    new: Any


def diff(a: Any, b: Any) -> list[DiffEntry]:
    """Return each path that was added, removed or changed between ``a`` and ``b``.

    Dictionaries are compared key by key, models field by field, lists and
    tuples index by index, and sets item by item (with the item as the last
    step of the path). Subtrees with the same hash on both sides are skipped.
    """
    out: list[DiffEntry] = []
    _diff(freeze(a), freeze(b), (), out)
    return out


def _same(a: Any, b: Any) -> bool:
    if a is b:
        return True
    ta = type(a)
    if ta is not type(b):
        return False
    if ta in SCALAR_TYPES:
        return a == b
    return node_hash(a) == node_hash(b)


def _diff(a: Any, b: Any, path: tuple[Any, ...], out: list[DiffEntry]) -> None:
    if _same(a, b):
        return
    t = type(a)
    if t is not type(b) or t in SCALAR_TYPES:
        out.append(DiffEntry(path, CHANGED, a, b))
        return
    if t is FrozenDict:
        for key, old in a.items():
            if key in b:
                _diff(old, b[key], path + (key,), out)
            else:
                out.append(DiffEntry(path + (key,), REMOVED, old, None))
        for key, new in b.items():
            if key not in a:
                out.append(DiffEntry(path + (key,), ADDED, None, new))
        return
    if t is FrozenList or t is FrozenTuple:
        for index in range(max(len(a), len(b))):
            if index >= len(b):
                out.append(DiffEntry(path + (index,), REMOVED, a[index], None))
            elif index >= len(a):
                out.append(DiffEntry(path + (index,), ADDED, None, b[index]))
            else:
                _diff(a[index], b[index], path + (index,), out)
        return
    if t is FrozenSet:
        for item in a:
            if item not in b:
                out.append(DiffEntry(path + (item,), REMOVED, item, None))
        for item in b:
            if item not in a:
                out.append(DiffEntry(path + (item,), ADDED, None, item))
        return
    info = model_info_of(a)
    if info is not None:
        for name, old, new in zip(info.fields, model_values(info, a), model_values(info, b)):
            _diff(old, new, path + (name,), out)
        return
    out.append(DiffEntry(path, CHANGED, a, b))
