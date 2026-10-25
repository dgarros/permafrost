# Proposal

## Why

Applications that keep one version of their data per branch need to hold hundreds or thousands of these versions in one process, and memory use must not grow with each version. The repository currently contains no implementation (the previous one was removed in commit `a41147b`), and `SPEC.md` now describes the library to build. This change implements the first version of Permafrost as described in `SPEC.md`, goals 1 to 11.

## What Changes

- Add read-only node classes for dictionaries, lists, tuples and sets, and a base class that user Pydantic dataclasses inherit from to support weak references.
- Convert any supported value (scalars, collections, Pydantic dataclasses, Pydantic models, types with a registered type handler) into a tree of read-only nodes, hash each node with BLAKE2b over a deterministic msgpack form, and store each node once in a registry that holds weak references.
- Add update operations that return a new version of a value: set at a path, delete at a path, and merge a partial value.
  - Dictionaries and models merge key by key at every level.
  - For lists, the caller selects "replace" or "append". "Append" puts the items of the new list after the items of the existing list. This rule is an assumption made for this change: `SPEC.md` says "merge the two lists" without saying how.
  - Incremental list update is not part of this change, because `SPEC.md` does not define it.
- Add equality by hash, a diff between two values that skips subtrees with the same hash, and a list of keys whose values differ between two dimensions.
- Add dimensions: a name that points to the root hash of a key map. The key map is a hash array mapped trie with up to 32 children per node, so creating a dimension from another copies one hash.
- Add an optional external cache with a pluggable `async` backend interface and a Redis backend that uses `redis.asyncio`.
- Write dimension root hashes to the external cache so that other processes can read a dimension, and add an operation that reloads a dimension's root hash from the external cache.
- Add an `async` loader that the application registers. Permafrost calls it on a cache miss with one dimension and one key.
- Add a cleanup operation that evicts values nobody has read for a configured time or when the in-memory cache passes a memory limit, and an optional `asyncio` helper that runs cleanup at a fixed interval.
- Update the merge section of `SPEC.md` to record the "append" rule for lists.

## Capabilities

### New Capabilities

- `frozen-values`: converting user values into read-only nodes, the supported types and type handlers, validation at the edge, hashing and serialization, and storing each node once in the registry.
- `value-updates`: set, delete and merge operations that return a new version of a value and share unchanged nodes with the previous version.
- `value-diff`: equality by hash and the diff between two values.
- `dimensions`: storing and reading values by key in a dimension, creating a dimension from another, the key map, and listing the keys that differ between two dimensions.
- `external-cache`: the backend interface, the Redis backend, fetching values level by level, writing new nodes in one request, and expiry times.
- `dimension-sharing`: writing dimension root hashes to the external cache, reading a dimension that another process wrote, and reloading a dimension's root hash on request.
- `value-loader`: the loader that the application registers and the behavior on a cache miss.
- `cache-cleanup`: eviction by idle time and by memory limit, read times, and the interval helper.

### Modified Capabilities

None. The project has no existing specs.

## Impact

- Code: new modules in `src/permafrost/`. The placeholder `hello()` function in `src/permafrost/__init__.py` is replaced by the public API.
- Dependencies: adds `msgpack`. Adds `redis` as an optional dependency group for the Redis backend. Adds `pytest-asyncio` to the development dependencies. Tests against Redis need a running Redis server or a test double.
- Documentation: `SPEC.md` merge section gains the list "append" rule.
- Not part of this change: the items listed in `SPEC.md` under "Out of scope", and incremental list update.
