"""Diff between two values."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .codec import is_scalar_type
from .nodes import FrozenDict, FrozenList, FrozenSet, FrozenTuple
from .ops import Step
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

    path: tuple[Step, ...]
    kind: Kind
    old: object
    new: object


def diff(a: object, b: object) -> list[DiffEntry]:
    """Return each path that was added, removed or changed between ``a`` and ``b``.

    Dictionaries are compared key by key, models field by field, lists and
    tuples index by index, and sets item by item (with the item as the last
    step of the path). Subtrees with the same hash on both sides are skipped.
    """
    out: list[DiffEntry] = []
    _diff(freeze(a), freeze(b), (), out)
    return out


def _same(a: object, b: object) -> bool:
    """Return whether two frozen values are equal: by value for scalars, by hash for nodes."""
    if a is b:
        return True
    ta = type(a)
    if ta is not type(b):
        return False
    if is_scalar_type(ta):
        return a == b
    return node_hash(a) == node_hash(b)


def _diff(a: object, b: object, path: tuple[Step, ...], out: list[DiffEntry]) -> None:
    """Append to ``out`` the differences between the frozen values ``a`` and ``b`` found at ``path``.

    When the two values are not of the same type, or are scalars, the whole path is one changed entry.
    """
    if _same(a, b):
        return
    if type(a) is not type(b) or is_scalar_type(type(a)):
        out.append(DiffEntry(path, CHANGED, a, b))
        return
    if isinstance(a, FrozenDict) and isinstance(b, FrozenDict):
        for key, old in a.items():
            if key in b:
                _diff(old, b[key], path + (key,), out)
            else:
                out.append(DiffEntry(path + (key,), REMOVED, old, None))
        for key, new in b.items():
            if key not in a:
                out.append(DiffEntry(path + (key,), ADDED, None, new))
        return
    if isinstance(a, (FrozenList, FrozenTuple)) and isinstance(b, (FrozenList, FrozenTuple)):
        for index in range(max(len(a), len(b))):
            if index >= len(b):
                out.append(DiffEntry(path + (index,), REMOVED, a[index], None))
            elif index >= len(a):
                out.append(DiffEntry(path + (index,), ADDED, None, b[index]))
            else:
                _diff(a[index], b[index], path + (index,), out)
        return
    if isinstance(a, FrozenSet) and isinstance(b, FrozenSet):
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
