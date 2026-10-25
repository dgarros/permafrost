# Proposal

## Why

The public API of Permafrost declares `Any` for every value it takes or returns, so a type checker cannot check the code that uses it: `store.get()` returns `Any`, `freeze(device)` returns `Any`, and a loader can return anything. `Any` appears 119 times in `src/permafrost/`, and `ty check` reports 40 errors, 34 of them in the library. `SPEC.md` names type checking of user code as a reason to prefer models (goal 4), and this change makes that promise hold for the whole API before the library has users whose code would break.

## What Changes

- Every public function and class declares exact parameter and return types. `Any` is removed from the library, and the lint configuration rejects it.
- The read-only collection classes get type parameters: `FrozenDict[K, V]`, `FrozenList[T]`, `FrozenTuple[T]` and `FrozenSet[T]`.
- `freeze()`, `set_in()`, `delete_in()` and `merge()` declare, through overloads, that a model goes in and the same model class comes out, that a scalar keeps its type, and that a `Mapping[K, V]` becomes a `FrozenDict[K, V]`, with the matching rule for sequences and sets.
- `Store` gets a type parameter for the type of its values: `Store[Device]` reads, writes, updates and loads `Device` values. The loader type follows.
- `register_type()` and `register_class()` are generic in the class they register, so `encode` and `decode` are checked against that class.
- Positions whose type cannot be known statically declare `object`, not `Any`: the old and new content of a diff entry, the new value given to `set_in()`, nodes in the registry, and data decoded from the external cache.
- `ty check` passes on the library, the tests and the examples, and runs with the tests.
- **BREAKING**: `set_in()` with an empty path raises `PathError` instead of returning the new value, so that `set_in()` on a model is typed as returning that model. `freeze(new)` gives what the empty path gave.
- **BREAKING**: `RedisBackend.from_url()` takes `prefix` and `node_ttl` as named parameters instead of `**kwargs`.
- The README gains a "Type checking" section that states the rule for exact types: declare values with models, scalars, or the abstract read-only types `Mapping`, `Sequence` and `AbstractSet`. A value declared as `list`, `dict` or `set` inside another value is typed as declared but holds the read-only class at run time, which the README already states for model fields.
- `SPEC.md` gains a goal for accurate static types.

## Capabilities

### New Capabilities

- `static-typing`: the types that a type checker reads for the public API: exact types for models, scalars and collections, a typed store and loader, typed type handlers, `object` where the type is open, and a type check that passes on the library, tests and examples.

### Modified Capabilities

- `value-updates`: the requirement "Set a value at a path" changes so that an empty path raises an error instead of replacing the whole value.

The main specs do not exist yet, because the change `initial-version` that creates them is not archived. The delta for `value-updates` is written against the `initial-version` delta of that capability, and `initial-version` must be archived before this change.

## Impact

- Code: every module in `src/permafrost/`. The node classes, `types.py`, `ops.py`, `diff.py`, `store.py` and `keymap.py` change the most. No change to the stored format, the hashes or the memory layout of nodes.
- Public API: type parameters on the four collection classes and `Store`; new public aliases for scalars and path steps; the two breaking changes above. Run-time behavior is otherwise unchanged.
- Tests and examples: four lines that pass a wrong type on purpose get a `ty` ignore comment; `tests/test_examples.py` skips the Redis example with a `skipif` mark; a type-level test module checks that the overloads resolve as intended; the examples declare their store and value types.
- Tooling: `[tool.ty]` in `pyproject.toml`, the Ruff rules `ANN401` and `TID251` that forbid `Any`, and `ty check` in the documented test command. No new dependency: `ruff` and `ty` are already in the development group.
- Documentation: README section "Type checking"; goal 12 in `SPEC.md`.
