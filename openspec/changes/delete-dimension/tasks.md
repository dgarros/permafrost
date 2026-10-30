# Tasks

## 1. Add `delete_root()` to the backends

- [ ] 1.1 In `src/permafrost/backends/base.py`, add `async def delete_root(self, dimension: str) -> None` to the `Backend` protocol, with a docstring that says it does nothing when the backend does not hold the root hash (design decision 4). Update the class docstring if it lists the operations.
- [ ] 1.2 In `src/permafrost/backends/memory.py`, add `MemoryBackend.delete_root()`, which removes the entry from `roots` if present and appends `"delete_root"` to `log`. Verify with a test in `tests/unit/test_external_cache.py` that `isinstance(MemoryBackend(), Backend)` still holds, that `delete_root()` removes a stored root hash, and that `delete_root()` of a name that was never set returns without error (spec scenario "Delete a root hash that the backend does not hold").
- [ ] 1.3 In `src/permafrost/backends/redis.py`, add `delete(self, *names: str) -> _Reply[int]` to the `RedisClient` protocol and `RedisBackend.delete_root()`, which runs `DEL` on `_dim_key(dimension)`. Verify with tests in `tests/unit/test_redis.py` (fakeredis) that the backend still passes `isinstance(redis_backend, Backend)`, that `delete_root()` removes the `test:dim:<name>` entry and leaves node entries, and that deleting a missing name returns without error.
- [ ] 1.4 Run `uv run ty check` and verify that `RedisBackend[Redis]` and `RedisBackend[FakeAsyncRedis]` still type-check with the new `delete` member of `RedisClient`.

## 2. Remove the lock of a dimension name when no task uses it

- [ ] 2.1 In `src/permafrost/store.py`, replace `_lock()` with `_locked(name)`, an async context manager that counts the tasks that hold or wait on the lock and removes the lock and its count when the count reaches 0 (design decision 2). Give it a docstring. Change every `async with self._lock(...)` in `create_dimension`, `reload`, `set`, `delete`, `update` and `_value` to `_locked`.
- [ ] 2.2 Verify with tests in `tests/unit/test_store.py` that `_locks` is empty after `create_dimension`, `set`, `delete` and `update` return, and that `_locks` is empty after the 20 concurrent updates of `test_concurrent_updates_in_one_process_do_not_overwrite_each_other`, which must still pass unchanged.

## 3. Delete a dimension

- [ ] 3.1 In `src/permafrost/store.py`, add `async def delete_dimension(self, name: str, *, evict_values: bool = False) -> None` with the steps of design decision 1: check that the dimension is in `_dims` or that the backend holds its root hash, else raise `DimensionNotFoundError`; await `backend.delete_root()`; remove the dimension from `_dims`. Give it a docstring that states what it removes, that node entries in the external cache expire on their own, and what `evict_values` does. Add it to the "Dimensions" part of the class, after `create_dimension`.
- [ ] 3.2 Verify with tests in `tests/unit/test_store.py` for the spec scenarios "Read a deleted dimension" (also check that the loader is not called), "Other dimensions keep their data", "Delete a dimension that does not exist", "Delete a dimension twice" and "Create a dimension again after deleting it".
- [ ] 3.3 Verify with a test in `tests/unit/test_store.py` for the spec scenario "Key map nodes are freed": record the hashes of the key map nodes of `branch-a` and `main` with `keymap.nodes()`, delete `branch-a`, drop the test's own references, run the `collect` fixture, and check with `registry.lookup()` that the nodes only `branch-a` referred to are gone and every node of `main` is still there.
- [ ] 3.4 Verify with tests in `tests/unit/test_sharing.py`, using `tests/process.py`, for the spec scenarios "Second process reads a deleted dimension", "Create a dimension that another process deleted", "Delete a dimension that is only in the external cache", "Another process holds the deleted dimension in memory", and "Failed deletion in the external cache" (a `MemoryBackend` subclass whose `delete_root()` raises, like the existing `FailingBackend`; check that the dimension is still readable afterwards).
- [ ] 3.5 Verify with a test in `tests/unit/test_sharing.py` for the spec scenario "Node entries stay in the external cache": after the deletion, every node entry is still in `backend.nodes`, `backend.log` holds no node deletion, and after `cleanup()` the hashes in `backend.touched` include no key map node that only the deleted dimension referred to.

## 4. Evict the values of a deleted dimension on request

- [ ] 4.1 In `src/permafrost/store.py`, add a private method that takes the deleted key map root and evicts the values that no other dimension in `_dims` refers to, with the three steps of design decision 3. Give it a docstring. Call it from `delete_dimension()` when `evict_values` is true, after the dimension is removed from `_dims`.
- [ ] 4.2 Verify with tests in `tests/unit/test_cleanup.py` for the spec scenarios "Dimension deleted without evicting its values", "Dimension deleted and its values evicted", "Value under two keys of the deleted dimension" and "Value that another dimension holds under another key". Also check that `cached_size` goes down by the size of the evicted values when a memory limit is set.
- [ ] 4.3 Verify with a test in `tests/unit/test_cleanup.py` that with 3 dimensions, a value that only the third dimension (not the first one compared) also holds is not evicted, so that the comparison does not stop after the first dimension.
- [ ] 4.4 Verify with a test in `tests/unit/test_sharing.py` for the spec scenario "Read after the values of a deleted dimension were evicted": process A holds only `branch-a`, process B created `main` with the same value, A deletes `branch-a` with `evict_values=True`, then A reads the value from `main` and gets it from the external cache without calling the loader.

## 5. Redis integration

- [ ] 5.1 In `tests/integration/test_redis.py`, add a test for the spec scenario "Delete a root hash in Redis": create a dimension with a value, delete it, and check that the `dim:` entry is gone, the node entries are still there with their time to live, and a second store on the same server raises `DimensionNotFoundError` on a read. Run it with `uv run pytest tests/integration` where Docker is available; otherwise state that it was not run.

## 6. Update the specification and the README

- [ ] 6.1 In `SPEC.md`, update goal 1 (a user deletes a dimension), goal 8 (the backend interface includes deleting the root hash of a dimension), goal 9 (deleting a dimension removes its root hash from the external cache, and other processes that hold it in memory keep it until they delete it) and goal 11 (the values of a deleted dimension stay in the value cache unless the user asks for them to be evicted). Verify by reading these sections against the spec deltas of this change.
- [ ] 6.2 In `README.md`, add `delete_dimension(name, evict_values=False)` to the list under "Dimensions" and a line to the Python example, add `delete_dimension()` to the `DimensionNotFoundError` entry under "Errors", and add `delete_root` to the "Writing a backend" example and text, stating that a backend must now provide it. Verify with `uv run pytest tests/unit/test_readme.py`, which runs every README example.

## 7. Integration checks

- [ ] 7.1 Run `uv run pytest`, `uv run ruff check` and `uv run ruff format --check`, and verify that all pass, including the type check. Check by reading the diff that every new function, method and class in `src/permafrost/` has a docstring, including those whose names start with `_`, and that no `typing.Any` was added.

## Workflow follow-up

- Decide in Infrahub whether `purge_inactive_branches()` passes `evict_values=True` (design, "Open Questions"). This is outside this repository.
- Archive the change after review.
