# Proposal

## Why

Infrahub plans to store its in-memory schema registry in Permafrost, with one dimension for each branch. When a branch is deleted, Infrahub removes its schema from memory, today in `SchemaManager.purge_inactive_branches()` ([issue #12](https://github.com/opsmill/permafrost/issues/12)). Permafrost has no operation that removes a dimension, so the schema of a deleted branch stays in memory for the life of the process. With an external cache, removing the key map root from memory alone is not enough: the next read fetches the dimension again from its root hash in the external cache, and `create_dimension()` with the same name raises `DimensionExistsError`. Infrahub cannot use Permafrost until a dimension can be deleted.

## What Changes

- New `Store.delete_dimension(name, *, evict_values=False)`. It removes the dimension from memory and, with an external cache, removes its root hash entry there. Python then frees the key map nodes that no other dimension refers to.
- Deleting a dimension that is neither in memory nor in the external cache raises `DimensionNotFoundError`, as `delete()` raises `KeyNotFoundError` for a missing key.
- By default, the values of the deleted dimension stay in the value cache until eviction removes them, as goal 11 of `SPEC.md` states today for the value of a deleted key. With `evict_values=True`, the store also evicts from the value cache the values that no other dimension in memory refers to.
- **BREAKING** for backends written by applications: the `Backend` protocol gets a required `delete_root(dimension)` method. `MemoryBackend` and `RedisBackend` implement it. A backend without it fails the type check and the `isinstance(backend, Backend)` check.
- The store removes the lock of a dimension name when no task uses it, so deleted dimensions leave no lock behind.
- Node entries in the external cache are not deleted. They expire on their own, because cleanup no longer extends the expiry time of the deleted key map.
- Not changed: another process that holds the deleted dimension in memory keeps it until it deletes it too. `reload()` in that process raises `DimensionNotFoundError` and leaves the dimension in its memory, as it does today when the root hash is missing.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `dimensions`: a new requirement to delete a dimension, and the "Any name can be a dimension" requirement states that a dimension exists until it is deleted.
- `dimension-sharing`: a new requirement that deleting a dimension removes its root hash from the external cache and does not delete its nodes there.
- `external-cache`: the "Pluggable backend interface" requirement adds the operation that removes the root hash of a dimension.
- `cache-cleanup`: the "Values that no dimension refers to" requirement adds the option to evict the values of a deleted dimension.

## Impact

- `src/permafrost/store.py`: the new `delete_dimension()` method, the eviction of the values of a deleted dimension, and the lock of each dimension name.
- `src/permafrost/backends/base.py`, `memory.py` and `redis.py`: the new `delete_root()` method. The `RedisClient` protocol adds the `delete` command.
- `SPEC.md`: goals 1, 8, 9 and 11.
- `README.md`: the "Dimensions", "Errors" and "Writing a backend" sections.
- Tests in `tests/unit/` and `tests/integration/test_redis.py`.
- No new dependency.
- Snapshots of a dimension ([issue #10](https://github.com/opsmill/permafrost/issues/10)) do not exist yet. Deleting a dimension only removes the store's own reference to its key map root, so a snapshot that holds its own root would keep working. The snapshot change decides this.
