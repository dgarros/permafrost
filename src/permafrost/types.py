"""Convert values into trees of read-only nodes, and rebuild nodes from their encoding."""

from __future__ import annotations

import dataclasses
import importlib
import sys
import weakref
from collections.abc import Callable, Iterable, Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel

from . import codec, registry
from .codec import SCALAR_TYPES, Ref
from .errors import UnsupportedTypeError
from .nodes import (
    COLLECTION_TYPES,
    KEYMAP_TYPES,
    FrozenDict,
    FrozenList,
    FrozenModel,
    FrozenSet,
    FrozenTuple,
    KMBranch,
    KMCollision,
    set_model_hash,
)

_BUILTIN_NODE_TYPES = frozenset(COLLECTION_TYPES + KEYMAP_TYPES)

# Hashes of nodes that have no slot for it (Pydantic models, dataclasses that do
# not inherit from FrozenModel, objects of registered types), by id().
_side_hashes: dict[int, bytes] = {}


def _attach_side_hash(obj: Any, h: bytes) -> None:
    key = id(obj)
    _side_hashes[key] = h
    weakref.finalize(obj, _side_hashes.pop, key, None)


def node_hash(node: Any) -> bytes:
    """Return the hash of a node."""
    h = getattr(node, "_pf_hash", None)
    if h is None:
        h = _side_hashes.get(id(node))
        if h is None:
            raise TypeError(f"{type(node).__qualname__} object is not a Permafrost node")
    return h


def is_node(value: Any) -> bool:
    if type(value) in _BUILTIN_NODE_TYPES:
        return True
    return getattr(value, "_pf_hash", None) is not None or id(value) in _side_hashes


def is_scalar(value: Any) -> bool:
    return type(value) in SCALAR_TYPES


# ---------------------------------------------------------------------------
# Models


@dataclass(slots=True)
class _ModelInfo:
    cls: type
    tag: int
    fields: tuple[str, ...]
    path: str
    slot: bool


_model_infos: dict[type, _ModelInfo | None] = {}
_classes_by_path: dict[str, type] = {}


def _check_weakref(cls: type) -> None:
    if cls.__weakrefoffset__ == 0:
        raise UnsupportedTypeError(
            f"{cls.__qualname__} does not support weak references: inherit from permafrost.FrozenModel"
        )


def _model_info(cls: type, path: str | None = None) -> _ModelInfo | None:
    if cls in _model_infos and path is None:
        return _model_infos[cls]
    info: _ModelInfo | None = None
    if dataclasses.is_dataclass(cls):
        if not cls.__dataclass_params__.frozen:  # type: ignore[attr-defined]
            raise UnsupportedTypeError(f"dataclass {cls.__qualname__} must be frozen")
        slot = issubclass(cls, FrozenModel)
        if not slot:
            _check_weakref(cls)
        fields = tuple(f.name for f in dataclasses.fields(cls))
        info = _ModelInfo(cls, codec.TAG_DATACLASS, fields, "", slot)
    elif issubclass(cls, BaseModel):
        if not cls.model_config.get("frozen"):
            raise UnsupportedTypeError(f"Pydantic model {cls.__qualname__} must be frozen")
        info = _ModelInfo(cls, codec.TAG_PYDANTIC_MODEL, tuple(cls.model_fields), "", False)
    if info is not None:
        info.path = path or f"{cls.__module__}:{cls.__qualname__}"
        _classes_by_path[info.path] = cls
    _model_infos[cls] = info
    return info


def register_class(cls: type, path: str | None = None) -> None:
    """Register a model class, optionally under a name of your choice.

    Permafrost writes the name in the encoding of each instance and uses it to
    find the class when it rebuilds an instance from the external cache. By
    default the name is ``module:qualname`` and the class is imported by that
    name. Register a class under another name when it cannot be imported, for
    example a class defined inside a function. Register it before storing any
    instance.
    """
    if _model_info(cls, path) is None:
        raise UnsupportedTypeError(f"{cls.__qualname__} is not a dataclass or a Pydantic model")


def _class_for_path(path: str) -> type:
    cls = _classes_by_path.get(path)
    if cls is None:
        module_name, _, qualname = path.partition(":")
        obj: Any = importlib.import_module(module_name)
        for part in qualname.split("."):
            obj = getattr(obj, part)
        cls = obj
        _model_info(cls)
    return cls


def _build_model(info: _ModelInfo, values: tuple[Any, ...], h: bytes) -> Any:
    cls = info.cls
    obj = cls.__new__(cls)
    if info.tag == codec.TAG_DATACLASS:
        for name, value in zip(info.fields, values):
            object.__setattr__(obj, name, value)
    else:
        object.__setattr__(obj, "__dict__", dict(zip(info.fields, values)))
        object.__setattr__(obj, "__pydantic_fields_set__", set(info.fields))
        object.__setattr__(obj, "__pydantic_extra__", None)
        object.__setattr__(obj, "__pydantic_private__", None)
    _attach_model_hash(info, obj, h)
    return obj


def _attach_model_hash(info: _ModelInfo, obj: Any, h: bytes) -> None:
    if info.slot:
        set_model_hash(obj, h)
    else:
        _attach_side_hash(obj, h)


def model_values(info: _ModelInfo, obj: Any) -> tuple[Any, ...]:
    return tuple(getattr(obj, name) for name in info.fields)


def model_info_of(obj: Any) -> _ModelInfo | None:
    return _model_info(type(obj))


def make_model(info: _ModelInfo, values: tuple[Any, ...], original: Any = None) -> Any:
    """Return the model node with these frozen field values."""
    data = codec.encode_model(info.tag, info.path, values, node_hash)
    h = codec.digest(data)
    node = registry.lookup(h)
    if node is not None:
        return node
    if original is not None and all(a is b for a, b in zip(values, model_values(info, original))):
        _attach_model_hash(info, original, h)
        node = original
    else:
        node = _build_model(info, values, h)
    return registry.add(h, node)


def _freeze_model(value: Any, info: _ModelInfo) -> Any:
    if is_node(value):
        return value
    if info.tag == codec.TAG_PYDANTIC_MODEL and value.__pydantic_extra__:
        raise UnsupportedTypeError(f"{info.cls.__qualname__} has extra fields, which Permafrost cannot store")
    values = tuple(freeze(v) for v in model_values(info, value))
    return make_model(info, values, original=value)


# ---------------------------------------------------------------------------
# Type handlers


@dataclass(frozen=True, slots=True)
class TypeHandler:
    """How to store objects of a type that Permafrost does not support on its own.

    ``encode`` returns a supported value that holds the content of the object.
    ``decode`` receives the frozen form of that value and returns an instance
    of the type. The instance must be read-only and support weak references.
    """

    type: type
    name: str
    encode: Callable[[Any], Any]
    decode: Callable[[Any], Any]


_handlers_by_type: dict[type, TypeHandler] = {}
_handlers_by_name: dict[str, TypeHandler] = {}


def register_type(cls: type, *, name: str, encode: Callable[[Any], Any], decode: Callable[[Any], Any]) -> TypeHandler:
    """Register a type handler for ``cls``. ``name`` identifies the type in stored data."""
    handler = TypeHandler(cls, name, encode, decode)
    _handlers_by_type[cls] = handler
    _handlers_by_name[name] = handler
    return handler


def _handler_inner(handler: TypeHandler, obj: Any) -> Any:
    return freeze(handler.encode(obj))


def _decode_handled(handler: TypeHandler, inner: Any, h: bytes) -> Any:
    obj = handler.decode(inner)
    try:
        weakref.ref(obj)
    except TypeError:
        raise UnsupportedTypeError(
            f"the decode function for {handler.name!r} must return an object that supports weak references"
        ) from None
    _attach_side_hash(obj, h)
    return obj


def _freeze_handled(value: Any, handler: TypeHandler) -> Any:
    if is_node(value):
        return value
    inner = _handler_inner(handler, value)
    h = codec.digest(codec.encode_handler(handler.name, inner, node_hash))
    node = registry.lookup(h)
    if node is not None:
        return node
    return registry.add(h, _decode_handled(handler, inner, h))


# ---------------------------------------------------------------------------
# Collections


def make_dict(data: dict[Any, Any]) -> FrozenDict:
    h = codec.digest(codec.encode_mapping(codec.TAG_DICT, data.items(), node_hash))
    node = registry.lookup(h)
    if node is not None:
        return node
    return registry.add(h, FrozenDict._new(data, h))


def make_list(items: tuple[Any, ...]) -> FrozenList:
    h = codec.digest(codec.encode_sequence(codec.TAG_LIST, items, node_hash))
    node = registry.lookup(h)
    if node is not None:
        return node
    return registry.add(h, FrozenList._new(items, h))


def make_tuple(items: tuple[Any, ...]) -> FrozenTuple:
    h = codec.digest(codec.encode_sequence(codec.TAG_TUPLE, items, node_hash))
    node = registry.lookup(h)
    if node is not None:
        return node
    return registry.add(h, FrozenTuple._new(items, h))


def make_set(items: frozenset[Any]) -> FrozenSet:
    h = codec.digest(codec.encode_set(items, node_hash))
    node = registry.lookup(h)
    if node is not None:
        return node
    return registry.add(h, FrozenSet._new(items, h))


def _freeze_mapping(value: Mapping[Any, Any]) -> FrozenDict:
    return make_dict({freeze(k): freeze(v) for k, v in value.items()})


def _freeze_items(value: Iterable[Any]) -> tuple[Any, ...]:
    return tuple(freeze(v) for v in value)


def freeze(value: Any) -> Any:
    """Return the read-only form of a value.

    Scalars are returned as they are. Dictionaries, lists, tuples and sets
    become ``FrozenDict``, ``FrozenList``, ``FrozenTuple`` and ``FrozenSet``.
    Models are returned as instances of their own class whose fields hold
    read-only values. Values that are already read-only are returned as they are.
    """
    t = type(value)
    if t in SCALAR_TYPES or t in _BUILTIN_NODE_TYPES:
        return value
    if t is dict:
        return _freeze_mapping(value)
    if t is list:
        return make_list(_freeze_items(value))
    if t is tuple:
        return make_tuple(_freeze_items(value))
    if t is set or t is frozenset:
        return make_set(frozenset(_freeze_items(value)))
    handler = _handlers_by_type.get(t)
    if handler is not None:
        return _freeze_handled(value, handler)
    info = _model_info(t)
    if info is not None:
        return _freeze_model(value, info)
    if isinstance(value, Mapping):
        return _freeze_mapping(value)
    if isinstance(value, list):
        return make_list(_freeze_items(value))
    if isinstance(value, tuple):
        return make_tuple(_freeze_items(value))
    if isinstance(value, AbstractSet):
        return make_set(frozenset(_freeze_items(value)))
    raise UnsupportedTypeError(f"Permafrost cannot store a value of type {t.__qualname__}")


def hash_of(value: Any) -> bytes:
    """Return the 16-byte content hash of a value."""
    if type(value) in SCALAR_TYPES:
        return codec.digest(codec.encode_scalar_root(value))
    if is_node(value):
        return node_hash(value)
    return hash_of(freeze(value))


def equal(a: Any, b: Any) -> bool:
    """Return whether two values have the same content, by comparing their hashes."""
    return hash_of(a) == hash_of(b)


# ---------------------------------------------------------------------------
# Walking nodes


def children(node: Any) -> list[Any]:
    """Return the child nodes of a node. Scalars are not returned."""
    t = type(node)
    if t is FrozenDict:
        return [x for kv in node._data.items() for x in kv if type(x) not in SCALAR_TYPES]
    if t in (FrozenList, FrozenTuple, FrozenSet):
        return [x for x in node._data if type(x) not in SCALAR_TYPES]
    if t is KMBranch:
        return [c for c in node.children if type(c) is not tuple]
    if t is KMCollision or t in SCALAR_TYPES:
        return []
    handler = _handlers_by_type.get(t)
    if handler is not None:
        inner = _handler_inner(handler, node)
        return [] if type(inner) in SCALAR_TYPES else [inner]
    info = _model_info(t)
    if info is not None:
        return [v for v in model_values(info, node) if type(v) not in SCALAR_TYPES]
    raise TypeError(f"{t.__qualname__} object is not a Permafrost node")


def encode_node(node: Any) -> bytes:
    """Return the encoded bytes of a node, or of a scalar that is the root of a value."""
    t = type(node)
    if t in SCALAR_TYPES:
        return codec.encode_scalar_root(node)
    if t is FrozenDict:
        return codec.encode_mapping(codec.TAG_DICT, node._data.items(), node_hash)
    if t is FrozenList:
        return codec.encode_sequence(codec.TAG_LIST, node._data, node_hash)
    if t is FrozenTuple:
        return codec.encode_sequence(codec.TAG_TUPLE, node._data, node_hash)
    if t is FrozenSet:
        return codec.encode_set(node._data, node_hash)
    if t is KMBranch:
        return codec.encode_km_branch(node.bitmap, node.children, node_hash)
    if t is KMCollision:
        return codec.encode_km_collision(node.entries)
    handler = _handlers_by_type.get(t)
    if handler is not None:
        return codec.encode_handler(handler.name, _handler_inner(handler, node), node_hash)
    info = _model_info(t)
    if info is not None:
        return codec.encode_model(info.tag, info.path, model_values(info, node), node_hash)
    raise TypeError(f"{t.__qualname__} object is not a Permafrost node")


def walk(root: Any) -> Iterable[Any]:
    """Yield each distinct node of a tree once, starting with the root."""
    seen: set[int] = set()
    stack = [root]
    while stack:
        node = stack.pop()
        if id(node) in seen:
            continue
        seen.add(id(node))
        yield node
        stack.extend(children(node))


def estimate_size(root: Any) -> int:
    """Return an estimate, in bytes, of the memory used by the nodes of a value."""
    total = 0
    for node in walk(root):
        total += sys.getsizeof(node)
        data = getattr(node, "_data", None)
        if data is not None:
            total += sys.getsizeof(data)
            items = data.items() if type(data) is dict else ((x,) for x in data)
            for item in items:
                total += sum(sys.getsizeof(x) for x in item if type(x) in SCALAR_TYPES)
        elif isinstance(node, BaseModel):
            total += sys.getsizeof(node.__dict__)
    return total


# ---------------------------------------------------------------------------
# Rebuilding nodes from their encoding


def build(h: bytes, payload: list[Any], resolve: Callable[[bytes], Any]) -> Any:
    """Rebuild a node from its decoded encoding.

    ``resolve`` returns the child node for a hash. The node is added to the
    registry as a node that is already in the external cache.
    """

    def r(item: Any) -> Any:
        return resolve(item.hash) if type(item) is Ref else item

    tag = payload[0]
    if tag == codec.TAG_SCALAR:
        return payload[1]
    node: Any
    if tag == codec.TAG_DICT:
        node = FrozenDict._new({r(k): r(v) for k, v in payload[1]}, h)
    elif tag == codec.TAG_LIST:
        node = FrozenList._new(tuple(map(r, payload[1])), h)
    elif tag == codec.TAG_TUPLE:
        node = FrozenTuple._new(tuple(map(r, payload[1])), h)
    elif tag == codec.TAG_SET:
        node = FrozenSet._new(frozenset(map(r, payload[1])), h)
    elif tag in (codec.TAG_DATACLASS, codec.TAG_PYDANTIC_MODEL):
        info = _model_info(_class_for_path(payload[1]))
        assert info is not None
        node = _build_model(info, tuple(map(r, payload[2])), h)
    elif tag == codec.TAG_HANDLER:
        node = _decode_handled(_handlers_by_name[payload[1]], r(payload[2]), h)
    elif tag == codec.TAG_KM_BRANCH:
        kids = tuple(r(c) if type(c) is Ref else (c[0], c[1]) for c in payload[2])
        node = KMBranch._new(payload[1], kids, h)
    elif tag == codec.TAG_KM_COLLISION:
        node = KMCollision._new(tuple((k, v) for k, v in payload[1]), h)
    else:
        raise ValueError(f"unknown node tag {tag}")
    return registry.add(h, node, created=False)
