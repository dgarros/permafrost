"""Operations that return a new version of a value.

Each operation leaves the previous version unchanged and creates new nodes
only for the changed node and its parents. Every other node is shared.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Literal

from .errors import PathError
from .nodes import FrozenDict, FrozenList, FrozenTuple
from .types import freeze, make_dict, make_list, make_model, make_tuple, model_info_of, model_values

ListMerge = Literal["replace", "append"]
Path = Sequence[Any]


def _child(node: Any, step: Any) -> Any:
    t = type(node)
    if t is FrozenDict:
        try:
            return node[step]
        except KeyError:
            raise PathError(f"key {step!r} not found") from None
    if t is FrozenList or t is FrozenTuple:
        if type(step) is not int:
            raise PathError(f"index {step!r} of a {t.__name__} must be an integer")
        try:
            return node[step]
        except IndexError:
            raise PathError(f"index {step} out of range") from None
    info = model_info_of(node)
    if info is not None:
        if step not in info.fields:
            raise PathError(f"{t.__qualname__} has no field {step!r}")
        return getattr(node, step)
    raise PathError(f"cannot follow step {step!r} into a value of type {t.__qualname__}")


def _replace(node: Any, step: Any, child: Any) -> Any:
    """Return ``node`` with ``child`` at ``step``. A dictionary gains the key if it is missing."""
    t = type(node)
    if t is FrozenDict:
        if step in node and node[step] is child:
            return node
        data = dict(node._data)
        data[freeze(step)] = child
        return make_dict(data)
    if t is FrozenList or t is FrozenTuple:
        _child(node, step)
        if node[step] is child:
            return node
        items = list(node._data)
        items[step] = child
        return make_list(tuple(items)) if t is FrozenList else make_tuple(tuple(items))
    info = model_info_of(node)
    if info is not None:
        if step not in info.fields:
            raise PathError(f"{t.__qualname__} has no field {step!r}")
        values = model_values(info, node)
        index = info.fields.index(step)
        if values[index] is child:
            return node
        return make_model(info, values[:index] + (child,) + values[index + 1 :])
    raise PathError(f"cannot update step {step!r} in a value of type {t.__qualname__}")


def _update_at(node: Any, path: tuple[Any, ...], change: Any) -> Any:
    """Apply ``change(parent, last_step)`` at the end of ``path`` and rebuild the parents."""
    if len(path) == 1:
        return change(node, path[0])
    step = path[0]
    child = _update_at(_child(node, step), path[1:], change)
    return _replace(node, step, child)


def set_in(value: Any, path: Path, new: Any) -> Any:
    """Return a new version of ``value`` with ``new`` at ``path``.

    A path is a sequence of steps: dictionary keys, list or tuple indexes and
    model field names. Setting a missing dictionary key adds it. Any other
    missing step raises ``PathError``.
    """
    root = freeze(value)
    new = freeze(new)
    path = tuple(path)
    if not path:
        return new
    return _update_at(root, path, lambda parent, step: _replace(parent, step, new))


def _delete(parent: Any, step: Any) -> Any:
    t = type(parent)
    if t is FrozenDict:
        if step not in parent:
            raise PathError(f"key {step!r} not found")
        return make_dict({k: v for k, v in parent.items() if k != step})
    if t is FrozenList or t is FrozenTuple:
        _child(parent, step)
        items = list(parent._data)
        del items[step]
        return make_list(tuple(items)) if t is FrozenList else make_tuple(tuple(items))
    if model_info_of(parent) is not None:
        raise PathError(f"cannot delete field {step!r}: a model field cannot be deleted")
    raise PathError(f"cannot delete step {step!r} from a value of type {t.__qualname__}")


def delete_in(value: Any, path: Path) -> Any:
    """Return a new version of ``value`` without the dictionary key or list item at ``path``."""
    path = tuple(path)
    if not path:
        raise PathError("cannot delete the root of a value")
    return _update_at(freeze(value), path, _delete)


def merge(value: Any, partial: Any, *, lists: ListMerge = "replace") -> Any:
    """Return a new version of ``value`` with ``partial`` merged into it.

    Dictionaries merge key by key and models field by field, at every level.
    Keys that exist only in ``partial`` are added to dictionaries. When both
    sides hold a list, ``lists="replace"`` keeps the list from ``partial`` and
    ``lists="append"`` adds its items after the existing items. Any other
    value in ``partial`` replaces the existing one.
    """
    if lists not in ("replace", "append"):
        raise ValueError(f"lists must be 'replace' or 'append', not {lists!r}")
    return _merge(freeze(value), partial, lists)


def _merge(base: Any, part: Any, lists: ListMerge) -> Any:
    tb = type(base)
    if tb is FrozenDict and isinstance(part, Mapping):
        data = dict(base._data)
        for k, v in part.items():
            fk = freeze(k)
            data[fk] = _merge(data[fk], v, lists) if fk in data else freeze(v)
        return make_dict(data)
    info = model_info_of(base)
    if info is not None:
        if type(part) is tb:
            fields = dict(zip(info.fields, model_values(info, part)))
        elif isinstance(part, Mapping):
            fields = dict(part)
        else:
            return freeze(part)
        values = list(model_values(info, base))
        for name, v in fields.items():
            if name not in info.fields:
                raise PathError(f"{tb.__qualname__} has no field {name!r}")
            index = info.fields.index(name)
            values[index] = _merge(values[index], v, lists)
        return make_model(info, tuple(values))
    if tb is FrozenList and lists == "append" and isinstance(part, (list, FrozenList)):
        return make_list(base._data + tuple(freeze(v) for v in part))
    return freeze(part)
