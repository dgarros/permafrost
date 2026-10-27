"""Convert values into trees of read-only nodes, and rebuild nodes from their encoding."""

from __future__ import annotations

import dataclasses
import importlib
import sys
import weakref
from collections.abc import Callable, Iterable, Iterator, Mapping, Sequence
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Protocol, TypeGuard, cast, overload, runtime_checkable

from pydantic import BaseModel

if TYPE_CHECKING:
    from _typeshed import DataclassInstance

from . import codec, registry
from .codec import EnumValue, Ref, Scalar, is_scalar_type
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
    KMChild,
    KMCollision,
    set_model_hash,
)

_BUILTIN_NODE_TYPES = frozenset(COLLECTION_TYPES + KEYMAP_TYPES)

# Hashes of nodes that have no slot for it (Pydantic models, dataclasses that do
# not inherit from FrozenModel, objects of registered types), by id().
_side_hashes: dict[int, bytes] = {}


def _attach_side_hash(obj: object, h: bytes) -> None:
    """Record the hash of a node that has no ``_pf_hash`` slot, until Python frees the node."""
    key = id(obj)
    _side_hashes[key] = h
    weakref.finalize(obj, _side_hashes.pop, key, None)


def node_hash(node: object) -> bytes:
    """Return the hash of a node."""
    h = getattr(node, "_pf_hash", None)
    if type(h) is bytes:
        return h
    h = _side_hashes.get(id(node))
    if h is None:
        raise TypeError(f"{type(node).__qualname__} object is not a Permafrost node")
    return h


def is_node(value: object) -> bool:
    """Return whether ``value`` is a node: a read-only collection, a key map node, or an object with a recorded hash."""
    if type(value) in _BUILTIN_NODE_TYPES:
        return True
    return getattr(value, "_pf_hash", None) is not None or id(value) in _side_hashes


def is_scalar(value: object) -> TypeGuard[Scalar]:
    """Return whether ``value`` is a scalar, which is stored inside its parent node rather than as a node."""
    return is_scalar_type(type(value))


# ---------------------------------------------------------------------------
# Models


@dataclass(frozen=True, slots=True)
class _ModelInfo:
    """What Permafrost needs to store instances of a dataclass or Pydantic model class.

    ``tag`` is the node tag of the class, ``fields`` the field names in order,
    ``path`` the name written in the encoding, and ``slot`` whether the class
    has a ``_pf_hash`` slot.
    """

    cls: type[object]
    tag: int
    fields: tuple[str, ...]
    path: str
    slot: bool


_model_infos: dict[type[object], _ModelInfo | None] = {}
_classes_by_path: dict[str, type[object]] = {}


class _DataclassParams(Protocol):
    """The ``__dataclass_params__`` attribute of a dataclass, as far as Permafrost reads it."""

    frozen: bool


@runtime_checkable
class _Dataclass(Protocol):
    """A dataclass, recognised by its ``__dataclass_params__`` attribute."""

    __dataclass_params__: _DataclassParams


def _check_weakref(cls: type) -> None:
    """Raise ``UnsupportedTypeError`` when instances of ``cls`` do not support weak references."""
    if cls.__weakrefoffset__ == 0:
        raise UnsupportedTypeError(
            f"{cls.__qualname__} does not support weak references: inherit from permafrost.FrozenModel"
        )


def _model_info(cls: type[object], path: str | None = None) -> _ModelInfo | None:
    """Return the model information of ``cls``, or ``None`` when it is not a dataclass or a Pydantic model.

    The result is cached by class. Passing ``path`` registers the class under
    that name. Raises ``UnsupportedTypeError`` when the class is not frozen, or
    is a dataclass whose instances do not support weak references.
    """
    if cls in _model_infos and path is None:
        return _model_infos[cls]
    path = path or f"{cls.__module__}:{cls.__qualname__}"
    info: _ModelInfo | None = None
    if dataclasses.is_dataclass(cls):
        if not (isinstance(cls, _Dataclass) and cls.__dataclass_params__.frozen):
            raise UnsupportedTypeError(f"dataclass {cls.__qualname__} must be frozen")
        slot = issubclass(cls, FrozenModel)
        if not slot:
            _check_weakref(cls)
        fields = tuple(f.name for f in dataclasses.fields(cls))
        info = _ModelInfo(cls, codec.TAG_DATACLASS, fields, path, slot)
    elif issubclass(cls, BaseModel):
        if not cls.model_config.get("frozen"):
            raise UnsupportedTypeError(f"Pydantic model {cls.__qualname__} must be frozen")
        info = _ModelInfo(cls, codec.TAG_PYDANTIC_MODEL, tuple(cls.model_fields), path, False)
    if info is not None:
        _classes_by_path[path] = cls
    _model_infos[cls] = info
    return info


def _is_enum_scalar_class(cls: type[object]) -> bool:
    """Return whether ``cls`` is an enum class that subclasses ``str`` or ``int``, whatever handler it has."""
    return issubclass(cls, Enum) and issubclass(cls, (str, int))


def register_class[M](cls: type[M], path: str | None = None) -> None:
    """Register a model class or an enum class, optionally under a name of your choice.

    Permafrost writes the name in the encoding of each instance and uses it to
    find the class when it rebuilds an instance from the external cache. By
    default the name is ``module:qualname`` and the class is imported by that
    name. Register a class under another name when it cannot be imported, for
    example a class defined inside a function. Register it before storing any
    instance. An enum class must subclass ``str`` or ``int``.
    """
    if _is_enum_scalar_class(cls):
        path = path or f"{cls.__module__}:{cls.__qualname__}"
        codec.register_enum(cls, path)
        _classes_by_path[path] = cls
        return
    if _model_info(cls, path) is None:
        raise UnsupportedTypeError(
            f"{cls.__qualname__} is not a dataclass, a Pydantic model or an enum class that subclasses str or int"
        )


def _class_for_path(path: str) -> type[object]:
    """Return the model class registered under ``path``, or import it by its ``module:qualname`` name."""
    cls = _classes_by_path.get(path)
    if cls is None:
        module_name, _, qualname = path.partition(":")
        obj: object = importlib.import_module(module_name)
        for part in qualname.split("."):
            obj = getattr(obj, part)
        if not isinstance(obj, type):
            raise ImportError(f"{path} is not a class")
        cls = obj
        if codec.enum_name(cls) is None:
            _model_info(cls)
    return cls


def _enum_member(item: EnumValue) -> object:
    """Return the enum member that ``item`` names, importing its class by name if needed.

    Raises ``ValueError`` when the class is not an enum class of scalars or the
    value is not one of its members.
    """
    cls = _class_for_path(item.name)
    if codec.enum_name(cls) is None or not issubclass(cls, Enum):
        raise _malformed(f"{item.name} is not an enum class that subclasses str or int")
    return cls(item.value)


def _scalar(item: object) -> object:
    """Return the decoded scalar ``item``, with the enum member for an ``EnumValue``."""
    return _enum_member(item) if type(item) is EnumValue else item


def _build_model(info: _ModelInfo, values: tuple[object, ...], h: bytes) -> object:
    """Create a model instance with these field values and hash ``h``, without its constructor or validation."""
    cls = info.cls
    obj = object.__new__(cls)
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


def _attach_model_hash(info: _ModelInfo, obj: object, h: bytes) -> None:
    """Record the hash ``h`` of a model node, in its slot when the class has one."""
    if info.slot:
        set_model_hash(obj, h)
    else:
        _attach_side_hash(obj, h)


def model_values(info: _ModelInfo, obj: object) -> tuple[object, ...]:
    """Return the field values of the model ``obj``, in field order."""
    return tuple(getattr(obj, name) for name in info.fields)


def model_info_of(obj: object) -> _ModelInfo | None:
    """Return the model information of the class of ``obj``, or ``None`` when it is not a model."""
    return _model_info(type(obj))


def make_model(info: _ModelInfo, values: tuple[object, ...], original: object = None) -> object:
    """Return the model node with these frozen field values."""
    data = codec.encode_model(info.tag, info.path, values, node_hash)
    h = codec.digest(data)
    node = registry.lookup(h, info.cls)
    if node is not None:
        return node
    if original is not None and all(a is b for a, b in zip(values, model_values(info, original))):
        _attach_model_hash(info, original, h)
        node = original
    else:
        node = _build_model(info, values, h)
    return registry.add(h, node)


def _freeze_model(value: object, info: _ModelInfo) -> object:
    """Return the read-only form of a model: an instance of its class whose fields hold read-only values."""
    if is_node(value):
        return value
    if isinstance(value, BaseModel) and value.__pydantic_extra__:
        raise UnsupportedTypeError(f"{info.cls.__qualname__} has extra fields, which Permafrost cannot store")
    values = tuple(freeze(v) for v in model_values(info, value))
    return make_model(info, values, original=value)


# ---------------------------------------------------------------------------
# Type handlers


@dataclass(frozen=True, slots=True)
class TypeHandler[T, E]:
    """How to store objects of a type that Permafrost does not support on its own.

    ``encode`` returns a supported value of type ``E`` that holds the content of
    the object. ``decode`` receives the frozen form of that value and returns an
    instance of the type. The instance must be read-only and support weak
    references. Declare ``E`` with read-only types, such as ``tuple`` or
    ``Sequence`` rather than ``list``, so that its type matches the frozen form
    that ``decode`` receives.
    """

    type: type[T]
    name: str
    encode: Callable[[T], E]
    decode: Callable[[E], T]


_handlers_by_type: dict[type[object], TypeHandler[object, object]] = {}
_handlers_by_name: dict[str, TypeHandler[object, object]] = {}


def register_type[T, E](
    cls: type[T], *, name: str, encode: Callable[[T], E], decode: Callable[[E], T]
) -> TypeHandler[T, E]:
    """Register a type handler for ``cls``. ``name`` identifies the type in stored data."""
    handler = TypeHandler(cls, name, encode, decode)
    # A handler takes priority over storing enum members as scalars.
    codec.exclude_enum(cls)
    # The registries hold handlers of every type, and a handler is only called
    # with instances of its own type or with the frozen form of its own encoding.
    stored = cast(TypeHandler[object, object], handler)
    _handlers_by_type[cls] = stored
    _handlers_by_name[name] = stored
    return handler


def _handler_inner(handler: TypeHandler[object, object], obj: object) -> object:
    """Return the frozen form of what ``handler`` encodes ``obj`` to."""
    return freeze(handler.encode(obj))


def _decode_handled(handler: TypeHandler[object, object], inner: object, h: bytes) -> object:
    """Return the object that ``handler`` decodes from ``inner``, with hash ``h``.

    Raises ``UnsupportedTypeError`` when the object does not support weak references.
    """
    obj = handler.decode(inner)
    try:
        weakref.ref(obj)
    except TypeError:
        raise UnsupportedTypeError(
            f"the decode function for {handler.name!r} must return an object that supports weak references"
        ) from None
    _attach_side_hash(obj, h)
    return obj


def _freeze_handled(value: object, handler: TypeHandler[object, object]) -> object:
    """Return the read-only node for an object of a type with a registered handler."""
    if is_node(value):
        return value
    inner = _handler_inner(handler, value)
    h = codec.digest(codec.encode_handler(handler.name, inner, node_hash))
    node = registry.lookup(h, handler.type)
    if node is not None:
        return node
    return registry.add(h, _decode_handled(handler, inner, h))


# ---------------------------------------------------------------------------
# Collections


def make_dict[K, V](data: dict[K, V]) -> FrozenDict[K, V]:
    """Return the dictionary node holding ``data``, whose keys and values must be frozen, reusing an existing node."""
    h = codec.digest(codec.encode_mapping(codec.TAG_DICT, data.items(), node_hash))
    node = registry.lookup(h, FrozenDict)
    if node is not None:
        return node
    return registry.add(h, FrozenDict._new(data, h))


def make_list[T](items: tuple[T, ...]) -> FrozenList[T]:
    """Return the list node holding ``items``, which must be frozen, reusing an existing node with the same hash."""
    h = codec.digest(codec.encode_sequence(codec.TAG_LIST, items, node_hash))
    node = registry.lookup(h, FrozenList)
    if node is not None:
        return node
    return registry.add(h, FrozenList._new(items, h))


def make_tuple[T](items: tuple[T, ...]) -> FrozenTuple[T]:
    """Return the tuple node holding ``items``, which must be frozen, reusing an existing node with the same hash."""
    h = codec.digest(codec.encode_sequence(codec.TAG_TUPLE, items, node_hash))
    node = registry.lookup(h, FrozenTuple)
    if node is not None:
        return node
    return registry.add(h, FrozenTuple._new(items, h))


def make_set[T](items: frozenset[T]) -> FrozenSet[T]:
    """Return the set node holding ``items``, which must be frozen, reusing an existing node with the same hash."""
    h = codec.digest(codec.encode_set(items, node_hash))
    node = registry.lookup(h, FrozenSet)
    if node is not None:
        return node
    return registry.add(h, FrozenSet._new(items, h))


def _freeze_mapping[K, V](value: Mapping[K, V]) -> FrozenDict[object, object]:
    """Return the dictionary node with the frozen form of each key and value of ``value``."""
    return make_dict({freeze(k): freeze(v) for k, v in value.items()})


def _freeze_items(value: Iterable[object]) -> tuple[object, ...]:
    """Return the frozen form of each item, in order."""
    return tuple(freeze(v) for v in value)


@overload
def freeze[S: Scalar](value: S) -> S: ...
@overload
def freeze[T](value: FrozenList[T]) -> FrozenList[T]: ...
@overload
def freeze[T](value: FrozenTuple[T]) -> FrozenTuple[T]: ...
@overload
def freeze[K, V](value: Mapping[K, V]) -> FrozenDict[K, V]: ...
@overload
def freeze[T](value: list[T]) -> FrozenList[T]: ...
@overload
def freeze[T](value: tuple[T, ...]) -> FrozenTuple[T]: ...
@overload
def freeze[T](value: Sequence[T]) -> Sequence[T]: ...
@overload
def freeze[T](value: AbstractSet[T]) -> FrozenSet[T]: ...
@overload
def freeze[M: FrozenModel | BaseModel | DataclassInstance](value: M) -> M: ...
@overload
def freeze(value: object) -> object: ...
def freeze(value: object) -> object:
    """Return the read-only form of a value.

    Scalars, including members of enum classes that subclass ``str`` or ``int``,
    are returned as they are. Dictionaries, lists, tuples and sets
    become ``FrozenDict``, ``FrozenList``, ``FrozenTuple`` and ``FrozenSet``.
    Models are returned as instances of their own class whose fields hold
    read-only values. Values that are already read-only are returned as they are.
    """
    t = type(value)
    if is_scalar_type(t) or t in _BUILTIN_NODE_TYPES:
        return value
    if type(value) is dict:
        return _freeze_mapping(value)
    if type(value) is list:
        return make_list(_freeze_items(value))
    if type(value) is tuple:
        return make_tuple(_freeze_items(value))
    if type(value) is set or type(value) is frozenset:
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


def hash_of(value: object) -> bytes:
    """Return the 16-byte content hash of a value."""
    if is_scalar(value):
        return codec.digest(codec.encode_scalar_root(value))
    if is_node(value):
        return node_hash(value)
    return hash_of(freeze(value))


def equal(a: object, b: object) -> bool:
    """Return whether two values have the same content, by comparing their hashes."""
    return hash_of(a) == hash_of(b)


# ---------------------------------------------------------------------------
# Walking nodes


def children(node: object) -> list[object]:
    """Return the child nodes of a node. Scalars are not returned."""
    if isinstance(node, FrozenDict):
        return [x for kv in node._data.items() for x in kv if not is_scalar_type(type(x))]
    if isinstance(node, (FrozenList, FrozenTuple, FrozenSet)):
        return [x for x in node._data if not is_scalar_type(type(x))]
    if isinstance(node, KMBranch):
        return [c for c in node.children if not isinstance(c, tuple)]
    t = type(node)
    if t is KMCollision or is_scalar_type(t):
        return []
    handler = _handlers_by_type.get(t)
    if handler is not None:
        inner = _handler_inner(handler, node)
        return [] if is_scalar_type(type(inner)) else [inner]
    info = _model_info(t)
    if info is not None:
        return [v for v in model_values(info, node) if not is_scalar_type(type(v))]
    raise TypeError(f"{t.__qualname__} object is not a Permafrost node")


def encode_node(node: object) -> bytes:
    """Return the encoded bytes of a node, or of a scalar that is the root of a value."""
    if is_scalar(node):
        return codec.encode_scalar_root(node)
    if isinstance(node, FrozenDict):
        return codec.encode_mapping(codec.TAG_DICT, node._data.items(), node_hash)
    if isinstance(node, FrozenList):
        return codec.encode_sequence(codec.TAG_LIST, node._data, node_hash)
    if isinstance(node, FrozenTuple):
        return codec.encode_sequence(codec.TAG_TUPLE, node._data, node_hash)
    if isinstance(node, FrozenSet):
        return codec.encode_set(node._data, node_hash)
    if isinstance(node, KMBranch):
        return codec.encode_km_branch(node.bitmap, node.children, node_hash)
    if isinstance(node, KMCollision):
        return codec.encode_km_collision(node.entries)
    t = type(node)
    handler = _handlers_by_type.get(t)
    if handler is not None:
        return codec.encode_handler(handler.name, _handler_inner(handler, node), node_hash)
    info = _model_info(t)
    if info is not None:
        return codec.encode_model(info.tag, info.path, model_values(info, node), node_hash)
    raise TypeError(f"{t.__qualname__} object is not a Permafrost node")


def walk(root: object) -> Iterator[object]:
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


def _scalars_size(items: Iterable[object]) -> int:
    """Return the memory, in bytes, of the scalars among ``items``."""
    return sum(sys.getsizeof(x) for x in items if is_scalar_type(type(x)))


def estimate_size(root: object) -> int:
    """Return an estimate, in bytes, of the memory used by the nodes of a value."""
    total = 0
    for node in walk(root):
        total += sys.getsizeof(node)
        if isinstance(node, FrozenDict):
            total += sys.getsizeof(node._data) + _scalars_size(x for kv in node._data.items() for x in kv)
        elif isinstance(node, (FrozenList, FrozenTuple, FrozenSet)):
            total += sys.getsizeof(node._data) + _scalars_size(node._data)
        elif isinstance(node, BaseModel):
            total += sys.getsizeof(node.__dict__)
    return total


# ---------------------------------------------------------------------------
# Rebuilding nodes from their encoding


def _malformed(what: str) -> ValueError:
    """Return the ``ValueError`` for a node from the external cache whose payload does not have the expected shape."""
    return ValueError(f"malformed node in the external cache: {what}")


def _field(payload: Sequence[object], index: int) -> object:
    """Return item ``index`` of a payload, or raise ``ValueError`` when the payload is too short."""
    if index >= len(payload):
        raise _malformed(f"missing field {index}")
    return payload[index]


def _as_list(value: object) -> Sequence[object]:
    """Return ``value`` when it is a list, or raise ``ValueError``."""
    if type(value) is not list:
        raise _malformed(f"expected an array, found {type(value).__qualname__}")
    return value


def _as_pair(value: object) -> tuple[object, object]:
    """Return the two items of ``value`` when it is a list of two, or raise ``ValueError``."""
    items = _as_list(value)
    if len(items) != 2:
        raise _malformed(f"expected a pair, found {len(items)} items")
    return items[0], items[1]


def _as_str(value: object) -> str:
    """Return ``value`` when it is a string, or raise ``ValueError``."""
    if type(value) is not str:
        raise _malformed(f"expected a string, found {type(value).__qualname__}")
    return value


def _as_int(value: object) -> int:
    """Return ``value`` when it is an integer, or raise ``ValueError``."""
    if type(value) is not int:
        raise _malformed(f"expected an integer, found {type(value).__qualname__}")
    return value


def _as_bytes(value: object) -> bytes:
    """Return ``value`` when it is ``bytes``, or raise ``ValueError``."""
    if type(value) is not bytes:
        raise _malformed(f"expected bytes, found {type(value).__qualname__}")
    return value


def build(h: bytes, payload: Sequence[object], resolve: Callable[[bytes], object]) -> object:
    """Rebuild a node from its decoded encoding.

    ``resolve`` returns the child node for a hash. The node is added to the
    registry as a node that is already in the external cache. Raises
    ``ValueError`` when the payload does not have the shape of its tag.
    """

    def r(item: object) -> object:
        """Return the child node for a ``Ref``, or the scalar ``item`` with enum members rebuilt."""
        return resolve(item.hash) if type(item) is Ref else _scalar(item)

    def km_child(item: object) -> KMChild:
        """Return a key map child: an entry ``(key, value_hash)``, or the branch or collision node of a ``Ref``."""
        if type(item) is not Ref:
            key, value_hash = _as_pair(item)
            return _as_str(key), _as_bytes(value_hash)
        child = resolve(item.hash)
        if type(child) is not KMBranch and type(child) is not KMCollision:
            raise _malformed(f"a key map branch refers to a {type(child).__qualname__}")
        return child

    tag = _as_int(_field(payload, 0))
    if tag == codec.TAG_SCALAR:
        return _scalar(_field(payload, 1))
    node: object
    if tag == codec.TAG_DICT:
        node = FrozenDict._new({r(k): r(v) for k, v in map(_as_pair, _as_list(_field(payload, 1)))}, h)
    elif tag == codec.TAG_LIST:
        node = FrozenList._new(tuple(map(r, _as_list(_field(payload, 1)))), h)
    elif tag == codec.TAG_TUPLE:
        node = FrozenTuple._new(tuple(map(r, _as_list(_field(payload, 1)))), h)
    elif tag == codec.TAG_SET:
        node = FrozenSet._new(frozenset(map(r, _as_list(_field(payload, 1)))), h)
    elif tag in (codec.TAG_DATACLASS, codec.TAG_PYDANTIC_MODEL):
        info = _model_info(_class_for_path(_as_str(_field(payload, 1))))
        if info is None:
            raise _malformed("the class of a model is not a dataclass or a Pydantic model")
        node = _build_model(info, tuple(map(r, _as_list(_field(payload, 2)))), h)
    elif tag == codec.TAG_HANDLER:
        handler = _handlers_by_name[_as_str(_field(payload, 1))]
        node = _decode_handled(handler, r(_field(payload, 2)), h)
    elif tag == codec.TAG_KM_BRANCH:
        kids = tuple(map(km_child, _as_list(_field(payload, 2))))
        node = KMBranch._new(_as_int(_field(payload, 1)), kids, h)
    elif tag == codec.TAG_KM_COLLISION:
        entries = tuple((_as_str(k), _as_bytes(v)) for k, v in map(_as_pair, _as_list(_field(payload, 1))))
        node = KMCollision._new(entries, h)
    else:
        raise _malformed(f"unknown node tag {tag}")
    return registry.add(h, node, created=False)
