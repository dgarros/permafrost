# Design

## Context

See `proposal.md` for the reason for this change and the files in `specs/` for the required behavior. The source is [issue #12](https://github.com/opsmill/permafrost/issues/12). The user decided the three points that the issue left open:

- Deleting a dimension that does not exist raises `DimensionNotFoundError`.
- The values of the deleted dimension stay in the value cache by default. An option evicts the values that no other dimension refers to.
- `delete_root()` is a required method of the `Backend` protocol.

What a dimension holds today, at commit `46f6db2`:

- `Store._dims` maps each dimension name to its key map root (`KMBranch`). This is the only strong reference to the key map that the store holds.
- `Store._locks` maps each dimension name to an `asyncio.Lock`. `_lock()` creates the lock on first use and never removes it. `create_dimension`, `reload`, `set`, `delete`, `update` and `_value` (when the loader returns a value with another hash) take it.
- With a backend, `Store._root()` reads the root hash with `backend.get_root()` when the dimension is not in `_dims`, and `create_dimension()` raises `DimensionExistsError` when `get_root()` returns a hash.
- `Store._extend_expiry()`, run by `cleanup()` with a backend, extends the expiry time of every key map node reachable from `_dims` and of the values read since the previous cleanup.
- The value cache (`_values`, `_read_at`, `_sizes`, `_total_size`) maps value hashes to value roots. It does not record which dimension or key refers to a value. `_evict(h)` removes one entry and its size.
- `keymap.items(root)` yields each `(key, value hash)` entry. `keymap.diff(a, b)` returns `(key, kind)` pairs for the keys whose value hashes differ, with `kind` one of `"added"`, `"removed"` and `"changed"`, and skips every subtree whose hash is the same on both sides.
- The `Backend` protocol (`backends/base.py`) is `runtime_checkable`. Tests check `isinstance(backend, Backend)` for `MemoryBackend` and `RedisBackend`, which checks that each protocol method exists.
- `RedisBackend` stores the root hash of a dimension under `<prefix>dim:<name>` with `SET` and no expiry time. The `RedisClient` protocol lists only the commands the backend uses: `get`, `mget`, `set` and `pipeline`.

## Goals / Non-Goals

**Goals:**

- Remove every reference that the store holds to a deleted dimension: its key map root, its lock and, with a backend, its root hash entry.
- Keep the cost of a deletion without `evict_values` independent of the size of the dimension.
- With `evict_values=True`, evict only values that no other dimension in memory refers to, at a cost that grows with how much the dimensions differ rather than with the number of keys times the number of dimensions.

**Non-Goals:**

- Deleting node entries from the external cache. Goal 11 of `SPEC.md` leaves their removal to the expiry time, so that a process cannot delete a node that another process still uses.
- Telling other processes that a dimension was deleted. Each process deletes the dimensions it holds in memory, as Infrahub's `purge_inactive_branches()` does in each worker.
- Changing `reload()` when the root hash is missing. It keeps raising `DimensionNotFoundError` and leaves the dimension in memory.
- Snapshots of a dimension ([issue #10](https://github.com/opsmill/permafrost/issues/10)), which do not exist yet.

## Decisions

### 1. The `delete_dimension()` method

```python
async def delete_dimension(self, name: str, *, evict_values: bool = False) -> None:
```

Steps, with the lock of `name` held:

1. Find out whether the dimension exists: it is in `_dims`, or the backend returns a root hash for it. Otherwise raise `DimensionNotFoundError(name)`.
2. With a backend, await `backend.delete_root(name)`.
3. Remove `name` from `_dims`, keeping the removed root in a local variable when `evict_values` is true.
4. With `evict_values`, evict the values described in decision 3, then drop the local variable.

The backend call comes before the change in memory, as in `_commit()`, which writes the root hash before it switches the dimension in memory. When the backend raises, the dimension stays in memory and in the external cache, and the application can try again.

Without a backend and with the dimension not in `_dims`, step 1 raises without any request. With a backend and the dimension in `_dims`, step 1 does not read the root hash from the backend, so a dimension that another process already deleted from the external cache is still deleted from memory without error. `delete_root()` of a missing entry does nothing (decision 4).

The method returns `None`, as `delete()` does. A test reads `cached_values` to check the eviction.

Alternative considered: return the number of evicted values, as `cleanup()` does. Without `evict_values` the number is always 0, so the return value would mean something only for one call form.

### 2. Remove the lock of a dimension name when no task uses it

Today a lock stays in `_locks` for every name ever used, including names of deleted dimensions. Removing the lock inside `delete_dimension()` is not safe: a task that waits on the lock still holds the old lock object, and a task that starts after the removal would create a new one, so two tasks could change the same dimension at the same time.

`_lock(name)` becomes `_locked(name)`, an async context manager that counts the tasks that hold or wait on the lock of `name`:

- On entry, it creates the lock if `_locks` has none, adds 1 to the count of `name`, and acquires the lock.
- On exit, it releases the lock, subtracts 1 from the count, and removes the lock and the count from their dictionaries when the count is 0.

Every caller of `_lock()` changes from `async with self._lock(name):` to `async with self._locked(name):`. The count makes the removal safe because a task that waits on the lock is counted. The store is used from one event loop (`SPEC.md`, "Out of scope"), so the count needs no other protection.

A consequence is that `_locks` holds only the names that a task is using, for every dimension, not only deleted ones.

Alternative considered: keep the lock of deleted names. One lock is small, but a process that creates and deletes branches for months would keep one lock for each branch name it ever used, which is what the issue asks to avoid.

### 3. Evict the values that no other dimension in memory refers to

The value cache does not record which dimension refers to a value, and counting references for each value would make creating a dimension cost one count update for each key, instead of copying one hash. The store computes the values to evict at the time of the deletion instead, by comparing key maps:

1. Candidates: for each `(key, value hash)` of the deleted key map (`keymap.items()`) whose hash is in `_values`, record the keys of the deleted dimension that hold each candidate hash.
2. For each other dimension in `_dims`, while candidates remain:
   - `changes = keymap.diff(deleted_root, other_root)`. The keys not in `changes` have the same value hash in both dimensions.
   - A candidate hash is referenced by the other dimension when at least one of its keys is not in `changes`. Remove it from the candidates.
   - For each key in `changes` with the kind `"added"` or `"changed"`, the other dimension holds `keymap.get(other_root, key)`. Remove that hash from the candidates. This covers a value that the other dimension holds under another key.
3. Evict each remaining candidate with `_evict()`.

Step 1 reads every key of the deleted dimension once. Step 2 reads, for each other dimension, only the key map nodes on the paths to the keys that differ, plus one pass over the remaining candidates. For branches created from `main`, the first comparison with `main` usually leaves only the values that the deleted branch changed, so the later comparisons check few candidates.

The whole computation runs without an `await`, so no other task changes `_dims` or the value cache during it.

Only dimensions in this process's memory count as references. With a backend, a dimension that only another process or the external cache holds can refer to an evicted value. A later read of it fetches the value from the external cache or calls the loader, as after any eviction. Without a backend, every dimension of the store is in memory, so the result is exact.

Values that the key map of the deleted dimension does not refer to, such as the earlier value of a key it changed, are not candidates. They stay until eviction, as goal 11 states.

Alternative considered: evict every value of the deleted dimension, whether or not other dimensions refer to it. It would make the next read of those values in other dimensions call the loader when there is no backend.

### 4. `delete_root()` in the backend protocol and the two backends

`Backend` gets a required method:

```python
async def delete_root(self, dimension: str) -> None:
    """Remove the root hash of a dimension. Do nothing when the backend does not hold it."""
```

- `MemoryBackend.delete_root()` removes the entry from `roots` if it is there, and appends `"delete_root"` to `log`, as `set_root()` appends `"set_root"`.
- `RedisBackend.delete_root()` runs `DEL <prefix>dim:<name>`. `DEL` of a missing key returns 0 without error. The `RedisClient` protocol adds `delete(self, *names: str) -> _Reply[int]`, which `redis.asyncio.Redis` and `fakeredis.FakeAsyncRedis` both provide.

A backend written by an application without this method no longer passes `isinstance(backend, Backend)` and fails the type check where it is passed to `Store`. The library is at version 0.1.0 and `SPEC.md` is a draft. `README.md` ("Writing a backend") lists the new method.

Alternative considered: call `delete_root()` only when the backend has it. The user chose a required method.

### 5. Expiry of the deleted key map in the external cache

No change is needed in `_extend_expiry()`: it walks `_dims`, so after the deletion it no longer extends the expiry time of the key map nodes that only the deleted dimension referred to. They expire after the node expiry time, 24 hours by default. Values of the deleted dimension that are still in the value cache and were read since the previous cleanup are still extended at the next cleanup, as for any read value.

## Risks / Trade-offs

- [A process that still holds the deleted dimension in memory writes to it after another process deleted it.] → Its write sets the root hash again, so the dimension exists again in the external cache. This is the same "last write wins" rule as for two processes changing one dimension (`SPEC.md`, goal 9). The calling application prevents it, for example by deleting the branch in every process before it accepts writes under the same name again.
- [`evict_values=True` reads every key of the deleted dimension once.] → The cost is about the same as `keys()` on that dimension, plus one key map comparison for each other dimension in memory. It runs only when the application asks for it.
- [A task waiting on the lock of a dimension that another task deletes.] → After the deletion, the waiting task finds no dimension and raises `DimensionNotFoundError`, or, for `create_dimension()`, creates it. The count of decision 2 keeps both tasks on the same lock.
- [Breaking change to the `Backend` protocol.] → Stated in `README.md`. A backend adds one method.

## Migration Plan

Applications with their own backend add `delete_root()`. No change to data: root hash entries and node entries already in the external cache keep their format.

Rollback: reverting the change removes `delete_dimension()`. Dimensions deleted before the rollback stay deleted, because their root hash entries are gone from the external cache.

## Open Questions

- Whether Infrahub should pass `evict_values=True` when it deletes a branch. This depends on whether it runs Permafrost with an external cache and with eviction turned on, which the issue does not say.
