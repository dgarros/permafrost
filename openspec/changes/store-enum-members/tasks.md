# Tasks

## 1. Encode and decode enum members in the codec

- [x] 1.1 In `src/permafrost/codec.py`, add the map from enum class to name, with a function that records a class under a name and a function that marks a class as not an enum scalar class (design decisions 1 and 5), and `is_enum_scalar_type(t)`, which checks `SCALAR_TYPES`, then the map, then `issubclass(t, Enum)` and `issubclass(t, (str, int))` once per class, recording `module:qualname` by default. Give each function a docstring. Verify with a unit test in `tests/unit/test_codec.py` that `is_enum_scalar_type` is true for `class X(str, Enum)`, `StrEnum`, `IntEnum` and `IntFlag` classes, and false for a plain `Enum`, a `class X(float, Enum)` and `object`.
- [x] 1.2 Add `EXT_ENUM = 5` and make `encode_item()` write a member of an enum scalar class as `ExtType(EXT_ENUM, pack([name, encode_item(member.value)]))`, before the `EXT_REF` branch. Verify with a test in `tests/unit/test_codec.py` that `hash_of({"s": State.PRESENT})` differs from `hash_of({"s": "present"})` and from the same dictionary holding a member of a second enum class with the value `"present"`, and that the existing hash tests still pass unchanged.
- [x] 1.3 Add the `EnumValue(name, value)` placeholder class (with `__slots__` and a docstring, like `Ref`) and decode `EXT_ENUM` into it in `_ext_hook()`, decoding the inner value with the same hook so that a large `int` value comes back as an `int`. Verify with a test that `unpack()` of an encoded node holding an enum member returns an `EnumValue` with the class name and value, and that `refs_in()` returns no hash for it.

## 2. Treat enum members as scalars when freezing, walking and rebuilding

- [x] 2.1 In `src/permafrost/types.py`, make `is_scalar()`, `freeze()`, `children()` and `_scalars_size()` use `codec.is_enum_scalar_type()` instead of `SCALAR_TYPES`. Verify with tests in `tests/unit/test_freeze.py` for the spec scenarios "Store a member of a str enum without registration", "Enum member as a model field" (the member is not in `children()` of the model), "Enum member as a dictionary key", "Integer enum member" and "Reject a member of an enum that does not subclass str or int".
- [x] 2.2 Make `register_class()` accept an enum scalar class and record it under `path` or `module:qualname`, and make `_class_for_path()` record an imported enum scalar class in the codec map. Update the `UnsupportedTypeError` message of `register_class()` to name enum classes that subclass `str` or `int`. Verify with a test that registers an enum class defined inside a function under a chosen name.
- [x] 2.3 Make `register_type()` mark its class as not an enum scalar class. Verify with a test for the spec scenario "Enum class with a registered type handler": with a handler for a `str` enum, the member is a node of its own and `hash_of()` returns the same hash as the encoding of `encode_handler()` gives today.
- [x] 2.4 In `build()`, make `r()` map an `EnumValue` to `cls(value)`, where `cls` comes from `_class_for_path(name)`, and raise `_malformed()` when the class is not an enum scalar class. Pass the item of the `TAG_SCALAR` branch through `r()`. Verify by adding enum members (as a dictionary key, a dictionary value, a list item, a model field, and an `IntFlag` composite value) to `test_decoding_returns_equal_content` in `tests/unit/test_codec.py`, and with a test that a value whose root is an enum member is rebuilt as the member. Also verify the test for the function-local enum class from 2.2 rebuilds its member.
- [x] 2.5 Update `SPEC.md` goal 3 ("Support deeply nested data") to list members of enum classes that subclass `str` or `int` among the scalars. Verify by reading the section against `specs/frozen-values/spec.md` of this change.

## 3. Compare enum members in diffs

- [x] 3.1 In `src/permafrost/diff.py`, make `_same()` and `_diff()` treat enum members as scalars. Verify with tests in `tests/unit/test_diff.py`: a model field changed from `State.PRESENT` to `State.ABSENT` gives one changed entry at the field path, and a change from `State.PRESENT` to `"present"` also gives one changed entry.

## 4. Read enum members from the external cache

- [x] 4.1 Verify, with tests in `tests/unit/test_external_cache.py` that use `tests/process.py`, the spec scenario "Read an enum member from the external cache" (the second process returns `State.PRESENT`, an instance of `State`) and the scenario "Enum class cannot be found when rebuilding" (an encoding that names an unknown class, and one whose value is not a member, are both treated as a cache miss and call the loader). Fix `store.py` only if one of these fails.

## 5. Document enum members

- [x] 5.1 In `README.md`, add members of enum classes that subclass `str` or `int` to "Supported types", state next to the sentence about `1`, `1.0` and `True` that an enum member and its plain value have different hashes, state that a type handler registered for an enum class takes priority, and mention in the `register_class()` text that it also accepts these enum classes. Add a Python example with a `str` enum used as a model field and a dictionary key. Verify with `uv run pytest tests/unit/test_readme.py`, which runs every README example.

## 6. Integration checks

- [x] 6.1 Run `uv run pytest`, `uv run ruff check` and `uv run ruff format --check`, and verify that all pass, including the type check. Check by reading the diff that every new function, method and class in `src/permafrost/` has a docstring, including those whose names start with `_`, and that no `typing.Any` was added.
- [x] 6.2 Verify with a test in `tests/unit/test_typing.py` that a type checker reports `State` as the type of `freeze(State.PRESENT)` and of a model field typed `State` after `freeze()`, with no change to `Scalar`.

## Workflow follow-up

- Check by running code that Infrahub's schema models, such as the attribute schema model with its four enum fields, freeze without error with this change. This needs the Infrahub repository and is not part of this change's tasks.
- Archive the change after review.
