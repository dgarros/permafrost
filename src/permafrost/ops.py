"""Operations that return a new version of a value.

Each operation leaves the previous version unchanged and creates new nodes
only for the changed node and its parents. Every other node is shared.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import TYPE_CHECKING, Literal, overload

from pydantic import BaseModel

from .codec import Scalar
from .errors import PathError
from .nodes import FrozenDict, FrozenList, FrozenModel, FrozenTuple
from .types import _ModelInfo, freeze, make_dict, make_list, make_model, make_tuple, model_info_of, model_values

if TYPE_CHECKING:
    from _typeshed import DataclassInstance

ListMerge = Literal["replace", "append"]
# A dictionary key, a list or tuple index, or a model field name. A tuple is a
# step because a dictionary key can be a tuple.
type Step = Scalar | tuple[Scalar, ...]
type Path = Sequence[Step]


def _field_name(info: _ModelInfo, node: object, step: Step) -> str:
    """Return ``step`` when it names a field of the model ``node``, or raise ``PathError``."""
    if not isinstance(step, str) or step not in info.fields:
        raise PathError(f"{type(node).__qualname__} has no field {step!r}")
    return step


def _index(node: FrozenList[object] | FrozenTuple[object], step: Step) -> int:
    """Return ``step`` when it is an integer index within ``node``, or raise ``PathError``."""
    if type(step) is not int:
        raise PathError(f"index {step!r} of a {type(node).__name__} must be an integer")
    if not -len(node) <= step < len(node):
        raise PathError(f"index {step} out of range")
    return step


def _child(node: object, step: Step) -> object:
    """Return the child of ``node`` at ``step``, or raise ``PathError`` when ``node`` has no such child."""
    if isinstance(node, FrozenDict):
        try:
            return node[step]
        except KeyError:
            raise PathError(f"key {step!r} not found") from None
    if isinstance(node, (FrozenList, FrozenTuple)):
        return node[_index(node, step)]
    info = model_info_of(node)
    if info is not None:
        return getattr(node, _field_name(info, node, step))
    raise PathError(f"cannot follow step {step!r} into a value of type {type(node).__qualname__}")


def _replace(node: object, step: Step, child: object) -> object:
    """Return ``node`` with ``child`` at ``step``. A dictionary gains the key if it is missing."""
    if isinstance(node, FrozenDict):
        if step in node and node[step] is child:
            return node
        data: dict[object, object] = dict(node._data)
        data[freeze(step)] = child
        return make_dict(data)
    if isinstance(node, (FrozenList, FrozenTuple)):
        index = _index(node, step)
        if node[index] is child:
            return node
        items: list[object] = list(node._data)
        items[index] = child
        return make_list(tuple(items)) if isinstance(node, FrozenList) else make_tuple(tuple(items))
    info = model_info_of(node)
    if info is not None:
        index = info.fields.index(_field_name(info, node, step))
        values = model_values(info, node)
        if values[index] is child:
            return node
        return make_model(info, values[:index] + (child,) + values[index + 1 :])
    raise PathError(f"cannot update step {step!r} in a value of type {type(node).__qualname__}")


def _update_at(node: object, path: tuple[Step, ...], change: Callable[[object, Step], object]) -> object:
    """Apply ``change(parent, last_step)`` at the end of ``path`` and rebuild the parents."""
    if len(path) == 1:
        return change(node, path[0])
    step = path[0]
    child = _update_at(_child(node, step), path[1:], change)
    return _replace(node, step, child)


@overload
def set_in[T](value: FrozenList[T], path: Path, new: object) -> FrozenList[T]: ...
@overload
def set_in[T](value: FrozenTuple[T], path: Path, new: object) -> FrozenTuple[T]: ...
@overload
def set_in[K, V](value: Mapping[K, V], path: Path, new: object) -> FrozenDict[K, V]: ...
@overload
def set_in[T](value: list[T], path: Path, new: object) -> FrozenList[T]: ...
@overload
def set_in[T](value: tuple[T, ...], path: Path, new: object) -> FrozenTuple[T]: ...
@overload
def set_in[T](value: Sequence[T], path: Path, new: object) -> Sequence[T]: ...
@overload
def set_in[M: FrozenModel | BaseModel | DataclassInstance](value: M, path: Path, new: object) -> M: ...
@overload
def set_in(value: object, path: Path, new: object) -> object: ...
def set_in(value: object, path: Path, new: object) -> object:
    """Return a new version of ``value`` with ``new`` at ``path``.

    A path is a sequence of steps: dictionary keys, list or tuple indexes and
    model field names. Setting a missing dictionary key adds it. Any other
    missing step raises ``PathError``, and so does an empty path: to replace a
    whole value, use ``freeze(new)``.
    """
    steps = tuple(path)
    if not steps:
        raise PathError("cannot set the root of a value: use freeze() on the new value")
    frozen_new = freeze(new)
    return _update_at(freeze(value), steps, lambda parent, step: _replace(parent, step, frozen_new))


def _delete(parent: object, step: Step) -> object:
    """Return ``parent`` without the dictionary key or list or tuple item at ``step``, or raise ``PathError``."""
    if isinstance(parent, FrozenDict):
        if step not in parent:
            raise PathError(f"key {step!r} not found")
        return make_dict({k: v for k, v in parent.items() if k != step})
    if isinstance(parent, (FrozenList, FrozenTuple)):
        index = _index(parent, step)
        items: list[object] = list(parent._data)
        del items[index]
        return make_list(tuple(items)) if isinstance(parent, FrozenList) else make_tuple(tuple(items))
    if model_info_of(parent) is not None:
        raise PathError(f"cannot delete field {step!r}: a model field cannot be deleted")
    raise PathError(f"cannot delete step {step!r} from a value of type {type(parent).__qualname__}")


@overload
def delete_in[T](value: FrozenList[T], path: Path) -> FrozenList[T]: ...
@overload
def delete_in[T](value: FrozenTuple[T], path: Path) -> FrozenTuple[T]: ...
@overload
def delete_in[K, V](value: Mapping[K, V], path: Path) -> FrozenDict[K, V]: ...
@overload
def delete_in[T](value: list[T], path: Path) -> FrozenList[T]: ...
@overload
def delete_in[T](value: tuple[T, ...], path: Path) -> FrozenTuple[T]: ...
@overload
def delete_in[T](value: Sequence[T], path: Path) -> Sequence[T]: ...
@overload
def delete_in[M: FrozenModel | BaseModel | DataclassInstance](value: M, path: Path) -> M: ...
@overload
def delete_in(value: object, path: Path) -> object: ...
def delete_in(value: object, path: Path) -> object:
    """Return a new version of ``value`` without the dictionary key or list item at ``path``."""
    steps = tuple(path)
    if not steps:
        raise PathError("cannot delete the root of a value")
    return _update_at(freeze(value), steps, _delete)


@overload
def merge[M: FrozenModel | BaseModel | DataclassInstance](
    value: M, partial: M | Mapping[str, object], *, lists: ListMerge = "replace"
) -> M: ...
@overload
def merge[K, V](
    value: Mapping[K, V], partial: Mapping[K, object], *, lists: ListMerge = "replace"
) -> FrozenDict[K, V]: ...
@overload
def merge(value: object, partial: object, *, lists: ListMerge = "replace") -> object: ...
def merge(value: object, partial: object, *, lists: ListMerge = "replace") -> object:
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


def _merge(base: object, part: object, lists: ListMerge) -> object:
    """Return the frozen ``base`` with the unfrozen ``part`` merged into it, as described in ``merge``."""
    if isinstance(base, FrozenDict) and isinstance(part, Mapping):
        data: dict[object, object] = dict(base._data)
        for k, v in part.items():
            fk = freeze(k)
            data[fk] = _merge(data[fk], v, lists) if fk in data else freeze(v)
        return make_dict(data)
    info = model_info_of(base)
    if info is not None:
        fields: dict[object, object]
        if type(part) is type(base):
            fields = dict(zip(info.fields, model_values(info, part)))
        elif isinstance(part, Mapping):
            fields = dict(part)
        else:
            return freeze(part)
        values = list(model_values(info, base))
        for name, v in fields.items():
            if not isinstance(name, str) or name not in info.fields:
                raise PathError(f"{type(base).__qualname__} has no field {name!r}")
            index = info.fields.index(name)
            values[index] = _merge(values[index], v, lists)
        return make_model(info, tuple(values))
    if isinstance(base, FrozenList) and lists == "append" and isinstance(part, (list, FrozenList)):
        return make_list(base._data + tuple(freeze(v) for v in part))
    return freeze(part)
