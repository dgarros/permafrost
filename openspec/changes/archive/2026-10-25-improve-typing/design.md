# Design

## Context

See `proposal.md` for the motivation and `specs/static-typing/spec.md` for the required behavior. The state that shapes the approach:

- `Any` appears 119 times in `src/permafrost/`. 60 of them are the public API, because the collection classes are `Mapping[Any, Any]`, `Sequence[Any]` and `Set[Any]`, and `Store` has no type parameter. The rest are the key map (typed with `object` and 9 `# type: ignore` comments), the sentinel `_MISSING`, the node registry, the model and handler registries, and the decoded msgpack payload.
- `ty check` (ty 0.0.91) reports 40 errors: 24 in `keymap.py`, 5 in `store.py`, 2 in `backends/redis.py`, 2 in `types.py`, 1 in `nodes.py`, 6 in tests and examples.
- ty does not read mypy-style `# type: ignore[code]` comments: the four test lines that carry one still report an error. ty reads `# ty: ignore[rule]`.
- Two probes against ty 0.0.91 confirmed what the design relies on: ty narrows `type(node) is C` in the negative branch when `C` is `@final`; a PEP 695 generic class with `__slots__` type-checks, and `object.__new__` creates its instances with no `__dict__`; an `Enum` sentinel narrows with `is`; recursive `type` aliases work.
- The project requires Python 3.12, so PEP 695 syntax (`class FrozenDict[K, V]`, `type Scalar = ...`) is available, and PEP 696 defaults for type parameters are not (Python 3.13).
- `ruff` and `ty` are in the development group. There is no CI workflow; `uv run pytest` is the documented check.
- The user decided: container overloads keep the declared item type (`Mapping[K, V]` becomes `FrozenDict[K, V]`), and `set_in()` with an empty path raises `PathError`.

## Goals / Non-Goals

**Goals:**

- No `Any` in `src/permafrost/`, enforced by Ruff rules `ANN401` and `TID251`.
- `ty check` passes on the library, tests and examples, and a failing type check fails `uv run pytest`.
- Exact types for models, scalars, and collections declared with abstract types. `object` where the type is open, never `Any`.
- No change to the stored format, the hashes, the memory layout of nodes, or run-time behavior other than the two breaking changes in the proposal.

**Non-Goals:**

- Support for type checkers other than ty. The annotations are standard, so mypy and Pyright should read them, but only ty is run and tested.
- Run-time validation of the type parameter of a store. `Store[Device]` is a declaration by the application; the library does not check what the external cache returns against it.
- Typing the content of a value at an arbitrary path (`set_in(..., new=...)`, `DiffEntry.old`). Python cannot express the type at a path.

## Decisions

### Type parameters on the node classes

`FrozenDict[K, V]`, `FrozenList[T]`, `FrozenTuple[T]` and `FrozenSet[T]` with PEP 695 syntax, inheriting from `Mapping[K, V]`, `Sequence[T]` and `Set[T]`. `Generic` and the ABCs declare empty `__slots__`, so instances keep the layout that `SPEC.md` measured. Variance is inferred: the classes are read-only, so `FrozenDict[str, Device]` is assignable to `Mapping[str, object]`.

- `_Frozen` declares `_pf_hash: bytes` as an annotation only; the subclasses keep the slot. This removes the `# type: ignore` in `__hash__`.
- `keys()`, `values()` and `items()` return `KeysView[K]`, `ValuesView[V]` and `ItemsView[K, V]`, which the built-in dictionary views satisfy. This removes three `# type: ignore[override]`.
- All six node classes (`FrozenDict`, `FrozenList`, `FrozenTuple`, `FrozenSet`, `KMBranch`, `KMCollision`) are `@final`. Nothing subclasses them, and finality lets ty narrow `type(x) is C` in both branches, so the key map keeps its `type() is` checks.
- `FrozenTuple[T]` has one item type. A `tuple[int, str]` freezes to `FrozenTuple[int | str]`. Alternative: a variadic `FrozenTuple[*Ts]`. Rejected, because `Sequence` is not variadic and the class would need two forms.

### Public type aliases

```python
type Scalar = str | int | float | bool | bytes | date | datetime | None  # codec.py
type Step = Scalar | tuple[Scalar, ...]  # ops.py
type Path = Sequence[Step]  # ops.py
type Loader[V] = Callable[[str, str], Awaitable[V]]  # store.py
```

All four are exported from `permafrost`. A tuple is a step because a dictionary key can be a tuple, which freezes to a `FrozenTuple` that compares and hashes like the tuple.

### Overloads on `freeze()`, `set_in()`, `delete_in()` and `merge()`

`freeze()` declares these overloads, in this order, because ty picks the first that matches:

1. `(value: S) -> S` for `S` bound to `Scalar`. Scalars come first because `str` and `bytes` are also sequences.
2. `(value: FrozenList[T]) -> FrozenList[T]` and `(value: FrozenTuple[T]) -> FrozenTuple[T]`, so that read-only sequences keep their class. A `FrozenDict` and a `FrozenSet` keep theirs through the next overloads.
3. `(value: Mapping[K, V]) -> FrozenDict[K, V]`.
4. `(value: list[T]) -> FrozenList[T]` and `(value: tuple[T, ...]) -> FrozenTuple[T]`.
5. `(value: Sequence[T]) -> Sequence[T]`. A value declared as `Sequence` can be a list or a tuple at run time, which freeze to different classes, so the result is only known to be a `Sequence`.
6. `(value: AbstractSet[T]) -> FrozenSet[T]`.
7. `(value: M) -> M` for `M` bound to `FrozenModel | BaseModel | DataclassInstance`, which covers Pydantic dataclasses, Pydantic models, and frozen dataclasses that do not inherit from `FrozenModel`.
8. `(value: object) -> object`. The fallback for objects of registered types. A type checker cannot know which classes a handler was registered for, so an unsupported type is still a run-time `UnsupportedTypeError`.

ty infers literal types for literal arguments: `freeze(1)` is `Literal[1]`, and `freeze({"a": 1})` is `FrozenDict[str, int]`.

The implementation signature takes and returns `object`. `set_in()` and `delete_in()` declare the same input-to-output mapping, with `path: Path` and `new: object`. `merge()` declares `(value: M, partial: M | Mapping[str, object]) -> M`, `(value: Mapping[K, V], partial: Mapping[K, object]) -> FrozenDict[K, V]`, the read-only equivalents, and `(value: object, partial: object) -> object`.

The item type is kept: `freeze()` on a `dict[str, list[int]]` is typed `FrozenDict[str, list[int]]` while the value holds a `FrozenList[int]`. The alternative, `FrozenDict[K, object]`, is always true but makes every read of a scalar an `isinstance` check, and the user rejected it. The README states the rule: declare nested containers as `Mapping`, `Sequence` or `AbstractSet`, which a `FrozenDict`, `FrozenList` or `FrozenSet` satisfies, and the types are exact.

### `set_in()` with an empty path raises

With the `M -> M` overload, returning `new` for an empty path would be a lie whenever `new` is of another type. `set_in()` raises `PathError` for an empty path, as `delete_in()` already does. `freeze(new)` gives what the empty path gave. The scenario "Set the root" in `tests/test_ops.py` becomes a scenario that expects the error, and `specs/value-updates/spec.md` records the new rule.

### `Store[V]`

`class Store[V]`. `get()` returns `V`, `set()` takes and returns `V`, `update()` takes `Callable[[V], V | Awaitable[V]]` and returns `V`, the loader is `Loader[V]`, and `diff()` returns `list[DiffEntry]`.

- There is no default for `V`, because PEP 696 needs Python 3.13. `Store()` with no annotation is inferred as `Store[Unknown]`, which ty treats like `Any`. The README shows `Store[Device](...)` and `store: Store[Device] = Store(loader=load_device)`.
- The caches hold `object`: they hold nodes without a type, and `freeze()` cannot map a type parameter to its read-only form, so inside the store `freeze(value)` on a `V` is `object`. Every value the store returns from `get()`, `set()` and `update()`, and the value it passes to the `change` function, goes through one method, `_typed()`, which casts to `V` with a comment: the type parameter is the application's declaration of what it stored under its keys. This is the one `cast` to a type parameter in the library.
- The dimension roots are `KMBranch`. A root hash fetched from the external cache that does not decode to a `KMBranch` raises `DimensionNotFoundError`, as a lost key map node does; this replaces an unchecked assumption with a check.
- The sentinel becomes `class _Missing(Enum): MISSING = auto()`, and `_fetch()` returns `object | _Missing`, which `is _Missing.MISSING` narrows. Alternative: `None`. Rejected, because `None` is a valid scalar root.

### Where `object` stays, and why

| Position | Type | Reason |
| --- | --- | --- |
| `DiffEntry.old`, `DiffEntry.new` | `object` | The type at a path cannot be known. `None` is also a valid value, so `object` rather than `object \| None`. |
| `set_in(..., new=...)` | `object` | Same. |
| Node registry, `Store._pending` | `object` | They hold every node type. `registry.lookup(h, cls: type[T]) -> T \| None` checks with `isinstance` and gives callers the exact type. The check is valid because a hash identifies an encoding, and the encoding starts with the type tag. One `isinstance` costs about 50 ns next to about 8 µs to freeze a node. |
| Decoded msgpack payload | `list[object]` | Data from the external cache is untrusted. `types.build()` narrows each field with `isinstance` and raises `ValueError` for an entry of the wrong shape, and `Store._fetch()` treats `ValueError` as a cache miss, as it does an import error. Today a wrong entry raises an `AttributeError` or `TypeError` from inside the decoder. |
| Handler registries | `TypeHandler[object, object]` | `TypeHandler[T, E]` is invariant, because `encode` takes `T` and returns `E` and `decode` takes `E` and returns `T`. `register_type()` casts once when it stores the handler, with a comment: the registries hold handlers of every type, and a handler is only called with instances of its own type or with the frozen form of its own encoding. |

`_ModelInfo` is not generic. It becomes a frozen dataclass whose `path` is computed before construction, with `cls: type[object]`. A type parameter would not help: the registry of model information is keyed by class at run time, so reading an entry back as `_ModelInfo[M]` would need a cast. The exact model type comes from the overloads of the public functions.

### Key map

- `type KMChild = Entry | KMBranch | KMCollision`, with `Entry = tuple[str, bytes]`. `KMBranch.children` is `tuple[KMChild, ...]`.
- `set()` and `delete()` take and return `KMBranch`: a root is always a branch, because collision nodes sit at depth 25. `_set()` and `_delete()` work on `KMChild` and `KMChild | None`.
- `_diff_nodes()`, `_child()` and `_entries()` take `KMChild | None`.
- The nine `# type: ignore` comments go away. The functions keep `type(x) is` checks, which `@final` makes narrow.

### Typed type handlers and model registration

`register_type[T, E](cls: type[T], *, name: str, encode: Callable[[T], E], decode: Callable[[E], T]) -> TypeHandler[T, E]` and `register_class[M](cls: type[M], path: str | None = None) -> None`. `E` is the type of the encoded value, so both functions are exact for the user, including lambdas, whose types ty infers from `cls`. `decode` receives the frozen form of the encoded value, so `E` follows the rule for exact types: declare it with `tuple`, `Sequence` or `Mapping`, not `list` or `dict`. `_build_model()` creates instances with `object.__new__(cls)`, which `BaseModel` and dataclasses accept, instead of `cls.__new__(cls)`, whose overloads ty cannot match. The frozen check reads `__dataclass_params__` through a runtime-checkable `Protocol` with a `frozen: bool` attribute, because the typeshed does not declare that attribute; `isinstance` narrows without a cast.

### Redis backend

`RedisBackend[C: RedisClient]` is generic in its client type, so `backend.client` keeps the exact type of the client the application passed. Tests and the Redis example call other commands through it (`ttl`, `ping`, `scan_iter`). `RedisClient` is a `Protocol` with the commands the backend calls (`get`, `mget`, `set`, `pipeline`, `aclose`), and `_Pipeline` covers `set`, `expire`, `execute` and the `async with` methods. `redis.asyncio.Redis` and `fakeredis.FakeAsyncRedis` satisfy both.

- The `redis` package declares each command as returning `X | Awaitable[X]`, because its synchronous and asynchronous clients share the declarations, and declares replies as `bytes | str`, because it cannot see `decode_responses=False`. The Protocol uses the same declarations. The backend awaits each reply through a small helper and checks that it is `bytes`. A client created with `decode_responses=True` now raises `TypeError` with the fix in the message, instead of storing text that breaks hashing.
- `from_url(url, *, prefix="permafrost:", node_ttl=DEFAULT_NODE_TTL)` replaces `**kwargs: Any` and returns `RedisBackend[Redis]`. The `TYPE_CHECKING` import of `redis` stays for that return type. It is never executed, so `import permafrost` still works without the `redis` package.

### Type-level tests

- `tests/test_typing.py` holds `typing.assert_type(...)` statements for each scenario of the spec: scalars, models, the four collections, a nested abstract declaration, a nested mutable declaration, the `object` fallback, `Store[Device]`, `Store[Mapping[str, int]]`, `register_type`. ty checks the assertions; at run time `assert_type` returns its argument, so pytest runs the file too.
- Scenarios that expect a type error (loader of another type, `encode` for another class, a list as a path step) are lines that carry `# ty: ignore[<rule>]`, with the ty rule `unused-ignore-comment` set to `error` in `[tool.ty.rules]`. If the error ever stops being reported, the unused ignore fails the check.
- `tests/test_type_check.py` runs the `ty` executable of the environment with `check` as a subprocess, as `tests/test_examples.py` runs the examples, so `uv run pytest` fails on a type error.

### Tooling

- `[tool.ty.environment] python-version = "3.12"` and `[tool.ty.rules] unused-ignore-comment = "error"` in `pyproject.toml`.
- `[tool.ruff.lint] extend-select = ["ANN401", "TID251"]` with `typing.Any` in `flake8-tidy-imports.banned-api`. `ANN401` reports `Any` only when it is the whole annotation (`x: Any`), not inside another type (`dict[str, Any]`, `Loader[Any]`); `TID251` reports every import of `Any`, so the two together catch every use.
- The deliberate wrong-type lines in `tests/test_model_base.py`, `tests/test_ops.py` and `examples/pydantic_models.py` carry `# ty: ignore[invalid-assignment]` or `# ty: ignore[invalid-argument-type]`. `tests/test_examples.py` skips the Redis example with a `pytest.mark.skipif` mark on its parameter, because ty does not resolve the parameters of `pytest.skip()` through pytest's decorator, in either form. `tests/test_external_cache.py` asserts that `_model_info()` returned a value before reading `.path`.

## Risks / Trade-offs

- [ty is at version 0.0.91 and its overload resolution or narrowing can change between releases.] → `uv.lock` pins the version, and `tests/test_typing.py` reports any change in what the overloads resolve to when ty is upgraded.
- [The `object` fallback of `freeze()` accepts any value, so storing an unsupported type is a run-time error, not a type error.] → Accepted. The set of registered types is only known at run time.
- [A nested `list`, `dict` or `set` declaration is typed as declared but holds the read-only class.] → The README states the rule and the exact alternative (`Sequence`, `Mapping`, `AbstractSet`), and the README already gives the same rule for model fields.
- [`Store()` with no annotation is `Store[Unknown]`, which turns the checker off for that store.] → The README shows the two ways to declare the type. A default type parameter can be added when the project moves to Python 3.13.
- [`FrozenTuple[T]` loses the per-position types of a mixed tuple.] → Accepted; mixed tuples are rare in stored data, and models are the recommended way to hold fields of different types.
- [`isinstance` in `registry.lookup()` and in `types.build()` adds work to the freeze and fetch paths.] → About 50 ns per lookup, measured against about 8 µs per node. The benchmark is rerun as a task.
- [`@final` on the node classes refuses subclassing.] → Nothing subclasses them, and `SPEC.md` says nodes are created only by Permafrost.

## Migration Plan

No users yet. The two breaking changes are listed in the proposal. For an application that relied on `set_in(value, (), new)`, the replacement is `freeze(new)`. For `RedisBackend.from_url(url, prefix=..., node_ttl=...)`, the call is unchanged; only other keyword arguments, which the backend never used, are refused.

## Open Questions

- When the project moves to Python 3.13, `Store[V = object]` could get a default so that `Store()` is `Store[object]` instead of `Store[Unknown]`. This does not change the specs or the tasks.
