# Proposal

## Why

Infrahub plans to store its in-memory schema registry in Permafrost, and its schema models have fields typed with enum classes that subclass `str` and `Enum`, such as `HashableModelState` ([issue #9](https://github.com/opsmill/permafrost/issues/9)). Permafrost treats a value as a scalar only when its exact type is a built-in scalar type, so `freeze()` raises `UnsupportedTypeError` on an enum member unless the application calls `register_type()` once for each enum class. With `register_type()`, each member is stored as a node of its own instead of inside its parent node. Infrahub cannot use Permafrost until this is fixed.

## What Changes

- A member of an enum class that subclasses `str` or `int` (this includes `StrEnum`, `IntEnum` and `IntFlag`) becomes a scalar. Permafrost stores it inside its parent node, as a dictionary key or value, a list, tuple or set item, a model field, or the whole value.
- The encoding of an enum member names its class and holds its value. The class name follows the rule for models: `module:qualname` by default, and the class is imported by that name when a node is rebuilt from the external cache.
- `register_class()` also accepts these enum classes, so that a class that cannot be imported by `module:qualname`, such as one defined inside a function, can be registered under another name.
- Rebuilding a node from its encoding returns the same enum member, not its plain value.
- An enum member and its plain value have different hashes, as `1` and `True` do today. Two members of different enum classes with the same value also have different hashes.
- A type handler registered with `register_type()` for an enum class keeps priority, so values stored through an existing handler keep their hashes.
- Enum classes that do not subclass `str` or `int` are not changed: they still need `register_type()`.
- The `Scalar` type alias and the `freeze()` overloads do not change, because a type checker already treats a member of a `str` or `int` enum as a `str` or an `int`.
- The encoding of values that contain no enum member does not change, so existing hashes and entries in the external cache stay valid.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `frozen-values`: the "Supported value types" requirement adds members of enum classes that subclass `str` or `int` to the scalars. A new requirement states how enum members are stored, hashed and rebuilt.

## Impact

- `src/permafrost/codec.py`: a new msgpack extension type for enum members, in `encode_item()` and in decoding.
- `src/permafrost/types.py`: `is_scalar()`, `freeze()`, `children()`, `_scalars_size()`, `register_class()`, the lookup of a class by its name, and `build()`.
- `src/permafrost/diff.py`: `_same()` and `_diff()`, which compare scalars by their exact type.
- `SPEC.md` (goal 3, "Support deeply nested data") and `README.md` ("Supported types", "Models" section on `register_class()`).
- Tests in `tests/unit/`.
- No new dependency. No change to the public types.
- Not checked: that Infrahub's schema models freeze without error once this change is in place. The issue states this was not run against the Infrahub models.
