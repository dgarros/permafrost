# Design

## Context

See `proposal.md` for the reason for this change and `specs/frozen-values/spec.md` for the required behavior.

How the code decides today whether a value is a scalar, at commit `5dd3e82`:

- `codec.SCALAR_TYPES` is a `frozenset` of exact types. Every check compares `type(value)` with it, so a member of `class State(str, Enum)`, whose type is `State`, is not a scalar.
- `codec.encode_item()` returns a scalar's msgpack form, or `ExtType(EXT_REF, hash)` for anything else. It tests each scalar type with `type(item) is ...`, so an enum member falls through to the reference branch.
- The other places that test the exact type are `types.is_scalar()`, `types.freeze()`, `types.children()`, `types._scalars_size()`, and `diff._same()` and `diff._diff()`. `store.py` calls `is_scalar()`, so it needs no change of its own.
- Extension type codes 1 to 4 are in use: `EXT_REF`, `EXT_DATE`, `EXT_DATETIME` and `EXT_BIGINT`. `codec._ext_hook()` decodes them while msgpack decodes a node.
- `codec.py` does not import `types.py`. Model classes are found by name in `types._class_for_path()`, which reads `_classes_by_path` and otherwise imports `module:qualname`.
- `store._fetch()` (around `store.py:449-472`) treats `ImportError`, `AttributeError`, `KeyError` and `ValueError` raised while it rebuilds a node as a cache miss.
- A type checker already treats a member of a `str` or `int` enum as a `str` or an `int`, so `freeze[S: Scalar](value: S) -> S` returns the enum class without any change to `Scalar`.

## Goals / Non-Goals

**Goals:**

- Store members of enum classes that subclass `str` or `int` inside their parent node, without registration.
- Keep the encoding, and so the hash, of every value that holds no enum member unchanged.
- Keep the cost of the scalar check low for values that are not enum members, because `freeze()`, `children()` and `encode_item()` run it on every item.

**Non-Goals:**

- Enum classes that subclass neither `str` nor `int`, and enums mixed with `float`, `bytes` or another type. They keep using `register_type()`.
- Detecting that an enum class changed between the process that wrote a value and the process that reads it, other than failing when the stored value is no longer a member.
- Changing the public types (`Scalar`, `Step`, `freeze()` overloads).

## Decisions

### 1. Which classes are enum scalars

A class is an enum scalar class when it is a subclass of `enum.Enum` and of `str` or `int`. This covers `class X(str, Enum)`, `StrEnum`, `IntEnum`, `IntFlag` and `class X(int, Enum)`.

The result is cached per class in a dictionary that maps the class to the name written in the encoding, or to `None` when the class is not an enum scalar class. A new `is_enum_scalar_type(t)` (in `codec.py`, so that `encode_item()` can use it without importing `types.py`) checks `t in SCALAR_TYPES` first, then the cache, then `issubclass` once per class. For values whose exact type is in `SCALAR_TYPES`, the cost does not change.

`codec.py` therefore holds the map from enum class to name. `types.register_class()` and `types._class_for_path()` write to it and read from it, which keeps the name rule for models and enums in one place in `types.py` while `codec.py` keeps no import of `types.py`.

Alternative considered: checking `isinstance(value, Enum)` on every item. It costs an `isinstance` call for every non-scalar item, such as every child node, which the per-class cache avoids.

### 2. Encoding: a new extension type holding the class name and the value

A member is written as `ExtType(EXT_ENUM, packed)`, where `EXT_ENUM = 5` and `packed` is the msgpack encoding of `[name, value]`:

- `name` is `module:qualname`, or the name given to `register_class()`.
- `value` is `encode_item(member.value, ...)`. For a `str` enum this is a msgpack string. For an `int` enum it is a msgpack integer, or an `EXT_BIGINT` extension when the value is outside the 64-bit range.

Because the type code is new, no existing encoding can match it, so a member and its plain value always differ, and the hash of a value without enum members does not change. Including the class name makes members of two classes with the same value differ.

Storing `member.value` rather than `member.name` lets `cls(value)` rebuild composite `IntFlag` values such as `Perm.R | Perm.W`, which have no single member name. A consequence is that renaming a member keeps its hash, and changing its value changes the hash.

Alternative considered: a new node tag with the member stored as a node of its own. This is what `register_type()` already gives, and the issue asks for members to be stored inside their parent node.

### 3. Decoding: a placeholder resolved in `build()`

`codec._ext_hook()` decodes `EXT_ENUM` into an `EnumValue(name, value)` placeholder, in the same way as it decodes `EXT_REF` into `Ref`. `codec.py` cannot import enum classes because the name lookup lives in `types.py`.

In `types.build()`, the local function `r()` already maps `Ref` to a child node. It also maps `EnumValue` to `cls(value)`, where `cls` comes from `_class_for_path(name)`. The `TAG_SCALAR` branch passes its single item through `r()` too, so that a value whose root is an enum member is rebuilt as the member.

`refs_in()` ignores `EnumValue`, because a member is not a child node.

Errors while rebuilding: an unknown name raises `ImportError` or `AttributeError`, and a value that is no longer a member raises `ValueError`. `store._fetch()` already treats all three as a cache miss. A class found by name that is not an enum scalar class raises `ValueError` through `_malformed()`.

### 4. Class names: the model rule, through `register_class()`

The user chose the same rule as for models. `register_class(cls, path=None)` accepts an enum scalar class and records it under `path`, or `module:qualname` by default. `_class_for_path()` already imports a class by `module:qualname`; after import it records the class in the enum name map when it is an enum scalar class, instead of only calling `_model_info()`.

`register_class()` keeps raising `UnsupportedTypeError` for any other class, with a message that also names enum classes that subclass `str` or `int`.

### 5. A registered type handler takes priority

An application may already call `register_type()` for an enum class, as the issue shows. `register_type()` records the class as not an enum scalar class in the cache of decision 1, so its members keep going through the handler, are stored as nodes of their own, and keep their hashes. Registering a handler for a class whose members were already stored as scalars applies to values frozen after the call.

Alternative considered: enum scalars before handlers. It would change the hash of every value stored through an existing handler, and would leave the handler registered but unused.

### 6. Places that compare exact types

Each check of `type(x) in SCALAR_TYPES` becomes a call to `is_enum_scalar_type(type(x))`, or to `is_scalar()` where a value is at hand:

- `codec.encode_item()`: test for an enum scalar before returning `EXT_REF`.
- `types.is_scalar()`, `freeze()`, `children()`, `_scalars_size()`.
- `diff._same()` and `diff._diff()`. `_same()` already returns `False` when the exact types differ, so `State.PRESENT` and `"present"` are reported as changed, which matches the different hashes.

`SCALAR_TYPES` stays as it is, because other code relies on it being the set of exact built-in types.

## Risks / Trade-offs

- [A `str` enum member is equal to its plain value in Python, and has the same Python hash, but has a different Permafrost hash.] → This matches how `1`, `1.0` and `True` behave today. `README.md` states it next to the existing sentence about `1`, `1.0` and `True`. A `FrozenDict` keyed by `State.PRESENT` still answers a lookup with `"present"`, because lookups use Python equality.
- [A dictionary `{State.PRESENT: 1, "present": 2}` has one key in Python, so the second entry replaces the first before Permafrost receives it.] → No change from Python's own behavior. No mitigation needed.
- [An enum class renamed or moved to another module cannot be found by name when a node is rebuilt.] → The read becomes a cache miss and the loader reloads the value, as for a renamed model class.
- [A `str` or `int` value that is no longer a member of its enum class after a code change.] → `cls(value)` raises `ValueError`, which is treated as a cache miss.
- [Enum classes that subclass `str` and override `__eq__` or `__hash__`.] → Not handled differently. Equality inside the library uses hashes, which depend only on the class name and the value.

## Migration Plan

No migration. Entries already in the external cache hold no enum members, except members stored through a type handler, and decision 5 keeps those unchanged. An application that registered a type handler for an enum class only to store it can remove the call; its values then get new hashes and are stored again under them.

Rollback: reverting the change makes `freeze()` reject enum members again. The older code decodes an unknown extension type as a raw `msgpack.ExtType` object instead of failing, so after a rollback, entries that contain `EXT_ENUM` must be removed from the external cache, for example by flushing it.

## Open Questions

- Whether Infrahub's schema models freeze without error with this change. The issue asks for this to be checked by running code against the Infrahub models, which this repository does not contain.
