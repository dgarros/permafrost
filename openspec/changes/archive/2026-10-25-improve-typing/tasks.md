# Tasks

## 1. Type check passes with the current API

- [x] 1.1 Add `[tool.ty.environment] python-version = "3.12"` and `[tool.ty.rules] unused-ignore-comment = "error"` to `pyproject.toml`; verify `uv run ty check` reads the settings (`uv run ty check --output-format concise` still reports the 40 known errors and no configuration error)
- [x] 1.2 In `keymap.py`, add the `KMChild` alias, type `KMBranch.children` as `tuple[KMChild, ...]`, mark the six node classes `@final`, declare `_pf_hash: bytes` on `_Frozen`, make `set()` and `delete()` take and return `KMBranch`, and remove the nine `# type: ignore` comments and the one in `_Frozen.__hash__`; verify `uv run ty check` reports no error in `keymap.py` and `nodes.py` and `uv run pytest tests/test_keymap.py tests/test_nodes.py` passes
- [x] 1.3 In `store.py`, replace `_MISSING` with the `_Missing` enum, type `_fetch()` as returning `object | _Missing`, check that a fetched dimension root is a `KMBranch` and raise `DimensionNotFoundError` otherwise, and restructure the `None` checks in `diff()`; verify `uv run ty check` reports no error in `store.py` and `uv run pytest tests/test_store.py tests/test_sharing.py` passes
- [x] 1.4 In `types.py`, create model instances with `object.__new__(cls)` and read `__dataclass_params__` through a `Protocol`; verify `uv run ty check` reports no error in `types.py` and `uv run pytest tests/test_freeze.py tests/test_model_base.py` passes
- [x] 1.5 In `backends/redis.py`, define the `_RedisClient` and `_Pipeline` protocols, type the client with them, drop the `TYPE_CHECKING` import, and give `from_url()` the named parameters `prefix` and `node_ttl`; verify `uv run ty check` reports no error in the backend, `uv run pytest tests/test_redis.py` passes, and the test that imports `permafrost` without `redis` still passes
- [x] 1.6 Add `# ty: ignore[<rule>]` to the four deliberate wrong-type lines in `tests/test_model_base.py`, `tests/test_ops.py` and `examples/pydantic_models.py`, skip the Redis example with a `skipif` mark in `tests/test_examples.py`, and assert the result of `_model_info()` in `tests/test_external_cache.py`; verify `uv run ty check` exits 0
- [x] 1.7 Add `tests/test_type_check.py`, which runs the `ty` executable of the environment with `check` as a subprocess and fails on a non-zero exit; verify `uv run pytest tests/test_type_check.py` passes, and fails when a file with a type error is added under `src/` and passes again when it is removed

## 2. Generic node classes, registries and codec

- [x] 2.1 Make `FrozenDict[K, V]`, `FrozenList[T]`, `FrozenTuple[T]` and `FrozenSet[T]` generic with PEP 695 syntax, and type `keys()`, `values()` and `items()` as the standard views without `# type: ignore`; verify `uv run ty check` passes, `uv run pytest tests/test_nodes.py` passes, and a new test checks that an instance of each class has no `__dict__` and accepts a weak reference
- [x] 2.2 Add the `Scalar` alias to `codec.py`, `Step` and `Path` to `ops.py`, and `Loader[V]` to `store.py`, and export the four from `permafrost`; verify `uv run python -c "from permafrost import Scalar, Step, Path, Loader"` exits 0
- [x] 2.3 Type the registry with `object`, add `registry.lookup(h, cls)` with the `isinstance` check, and use it in `make_dict()`, `make_list()`, `make_tuple()`, `make_set()`, `make_branch()` and `make_collision()`; verify `uv run ty check` passes and `uv run pytest tests/test_registry.py tests/test_freeze.py` passes
- [x] 2.4 Make `_ModelInfo` a frozen dataclass, `register_class[M]` generic, `TypeHandler[T, E]` generic and `register_type[T, E]` generic with the one documented `cast` when it stores the handler; verify `uv run ty check` passes and `uv run pytest tests/test_freeze.py` passes
- [x] 2.5 In `codec.py`, add a `Packable` alias for what msgpack accepts, type `hash_of_node` as `Callable[[object], bytes]`, type the decoded payload as `list[object]`, make `types.build()` narrow each field with `isinstance` and raise `ValueError` for an entry of the wrong shape, and make `Store._fetch()` treat `ValueError` as a cache miss; verify `uv run ty check` passes, `uv run pytest tests/test_codec.py` passes, and a new test in `tests/test_external_cache.py` stores a malformed entry under a value hash and checks that the read calls the loader
- [x] 2.6 Remove the remaining `Any` from `types.py`, `diff.py`, `ops.py`, `registry.py` and `store.py` internals and add `extend-select = ["ANN401", "TID251"]` under `[tool.ruff.lint]` with `typing.Any` banned; verify `uv run ruff check src --select ANN401,TID251` reports errors only in the public functions that group 3 and task 4.1 change, and `uv run pytest` passes

## 3. Public functions with exact types

- [x] 3.1 Declare the eight overloads of `freeze()` in the order the design gives, and type `hash_of()` and `equal()` with `object`; verify `uv run ty check` passes and `tests/test_typing.py` asserts with `assert_type` the types for a scalar, a model, a `dict[str, int]`, a `dict[str, Sequence[int]]`, a `dict[str, list[int]]`, a list, a tuple, a set, a read-only input and a registered type
- [x] 3.2 Declare the overloads of `set_in()` and `delete_in()`, type `path` as `Path` and `new` as `object`, and make `set_in()` raise `PathError` for an empty path; verify `uv run ty check` passes, `tests/test_typing.py` asserts the model and dictionary cases and carries a `# ty: ignore` line for a list as a path step, and `tests/test_ops.py` replaces the "Set the root" test with one that expects `PathError`
- [x] 3.3 Declare the overloads of `merge()`; verify `uv run ty check` passes and `tests/test_typing.py` asserts the model and dictionary cases
- [x] 3.4 Type `DiffEntry` with `tuple[Step, ...]` for the path and `object` for the old and new content, and `diff()` with `object` parameters; verify `uv run ty check` passes, `tests/test_typing.py` asserts `object` for the content, and `uv run pytest tests/test_diff.py` passes
- [x] 3.5 Update the README sections "Read-only values", "Changing values" and "Comparing values" where the examples or text no longer match (empty path, type of diff content); verify `uv run pytest tests/test_readme.py` passes

## 4. Typed store, documentation and enforcement

- [x] 4.1 Make `Store[V]` generic, type `get()`, `set()`, `update()`, the loader and the value cache with `V`, and cast values to `V` in one method, `_typed()`, with the documented comment; verify `uv run ty check` passes, `tests/test_typing.py` asserts `Device` for `Store[Device].get()` and `Mapping[str, int]` for `Store[Mapping[str, int]].get()`, and carries a `# ty: ignore` line for a loader that returns `str`
- [x] 4.2 Declare the store and value types in the three examples; verify `uv run ty check` passes and `uv run pytest tests/test_examples.py` passes
- [x] 4.3 Add the README section "Type checking" with the rule for exact types, the mutable-declaration exception, the two ways to declare `Store[Device]`, and the `register_type` signature; verify `uv run pytest tests/test_readme.py` runs the section's example and passes
- [x] 4.4 Add goal 12 "Accurate static types" to `SPEC.md` and the `uv run ty check` command to `AGENTS.md`; verify `git diff SPEC.md AGENTS.md` shows only these additions
- [x] 4.5 Run `uv run python benchmarks/dimensions.py`; verify the memory per dimension and the time per model node are within 10% of the values recorded in the `initial-version` change (186 bytes per dimension, about 8 µs per node)
- [x] 4.6 Run `uv run pytest`, `uv run ruff check`, `uv run ruff format --check src tests examples`, `uv run ty check` and `openspec validate improve-typing --strict`; verify that all pass except `ruff check`, that `ruff check` reports only the 23 errors that existed before this change, and that `grep -rw Any src/permafrost` finds nothing

## Workflow follow-up

- Fix the 23 Ruff errors that existed before this change, in a separate change that also chooses which Ruff rules the project enables.
- Archive this change with `/opsx:archive` after review.
