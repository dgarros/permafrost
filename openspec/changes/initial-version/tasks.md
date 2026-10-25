# Tasks

## 1. Project setup

- [x] 1.1 Add `msgpack` to the runtime dependencies, an optional `redis` group with `redis>=5`, and `pytest-asyncio` and `fakeredis` to the development group in `pyproject.toml`; verify `uv sync --all-extras` succeeds and `uv run python -c "import msgpack, redis, fakeredis, pytest_asyncio"` exits with code 0
- [x] 1.2 Create the module files listed under "Module layout" in `design.md` and a `tests/` directory, configure `asyncio_mode = "auto"` for pytest, and remove the placeholder `hello()` function; verify `uv run pytest` runs with no collection error
- [x] 1.3 Update the merge section of `SPEC.md` to record the "replace" and "append" list behaviors and the "replace" default, and update goal 11 to say the value cache records the last read time; verify `git diff SPEC.md` shows only these changes

## 2. Read-only nodes, encoding and registry (`frozen-values`)

- [x] 2.1 Implement `FrozenDict`, `FrozenList`, `FrozenTuple` and `FrozenSet` in `nodes.py` with `__slots__` that include `__weakref__`; verify tests show that every method that changes content raises an error, that read operations and equality with built-in values work, and that `weakref.ref()` accepts each instance
- [x] 2.2 Implement the `FrozenModel` base class for Pydantic dataclasses; verify a test that a frozen, slotted Pydantic dataclass inheriting from it still validates when called, has no `__dict__`, accepts a weak reference, and raises an error on field assignment
- [x] 2.3 Implement the deterministic msgpack encoding and BLAKE2b hashing in `codec.py`, covering every scalar type, the four collections, Pydantic dataclasses and Pydantic models; verify tests that dictionaries and sets with the same content in different insertion orders encode to the same bytes, that `[1, 2]` and `(1, 2)` have different hashes, and that decoding returns equal content
- [x] 2.4 Implement the weak registry in `registry.py`; verify a test that a node disappears from the registry after its last strong reference is deleted
- [x] 2.5 Implement `freeze()` and `hash_of()` in `types.py`, including creation of model instances without validation, reuse of existing nodes from the registry, and the error for unsupported types; verify tests for each scenario of `specs/frozen-values/spec.md`, including that `__post_init__` does not run and that two equal nested dictionaries are the same object
- [x] 2.6 Implement type handler registration; verify the "Store an object with a registered handler" scenario as a test
- [x] 2.7 Document freezing, the supported types, the `FrozenModel` base class, type handlers and the `list` field caveat from `design.md` in `README.md`; verify each code example in that section runs as written

## 3. Update operations (`value-updates`)

- [x] 3.1 Implement path resolution and `set_in()` in `ops.py`; verify tests for the path, set and "Set a field that the model does not have" scenarios of `specs/value-updates/spec.md`
- [x] 3.2 Implement `delete_in()`; verify tests for the delete scenarios, including the error when deleting a model field
- [x] 3.3 Implement `merge()` with the `lists="replace"` default and the `"append"` option; verify tests for every merge scenario
- [x] 3.4 Verify node sharing and "no change returns the same hash" with tests that check object identity of unchanged sibling subtrees after `set_in()` and `merge()`
- [x] 3.5 Document the update operations and the list merge behaviors in `README.md`; verify each code example runs as written

## 4. Diff of values (`value-diff`)

- [x] 4.1 Implement `diff()` in `diff.py` for dictionaries, lists, tuples, sets, models and type changes, returning entries with path, kind, old content and new content; verify tests for every scenario of `specs/value-diff/spec.md` except the dimension scenario
- [x] 4.2 Verify that the diff skips identical subtrees with a test that counts child reads on a value of 1,000 subtrees with one change
- [x] 4.3 Document equality by hash and `diff()` in `README.md`; verify each code example runs as written

## 5. Key map (`dimensions`, key map part)

- [x] 5.1 Implement the key map in `keymap.py`: insert, delete with collapse of single-leaf branches, lookup, iteration over keys, and collision nodes; verify property-style tests that 1,000 random insert and delete sequences that end with the same set of keys produce the same root hash
- [x] 5.2 Implement the comparison of two key maps that returns added, removed and changed keys and skips subtrees with the same hash; verify tests that count the nodes read when one key differs among 10,000
- [x] 5.3 Verify with a test that storing one key in a key map of 10,000 keys creates on average at most 4 new key map nodes

## 6. Store and dimensions in one process (`dimensions`, `value-loader`)

- [x] 6.1 Implement `Store` in `store.py` with `create_dimension`, `set`, `get`, `delete`, `update`, `keys`, `root_hash` and the per-dimension `asyncio.Lock`, without an external cache; verify tests for every scenario of `specs/dimensions/spec.md` that does not involve another process
- [x] 6.2 Implement `diff_keys()` and `diff()` on `Store`; verify tests for "Keys that differ between two dimensions" and the "Key changed on a branch" scenario of `specs/value-diff/spec.md`
- [x] 6.3 Implement the value cache with last read times and the read path value cache → registry → loader; verify tests for every scenario of `specs/value-loader/spec.md`
- [x] 6.4 Verify with a test that creating 1,000 dimensions from one dimension of 10,000 keys does not increase the number of nodes in the registry
- [x] 6.5 Document `Store`, dimensions, the loader and the errors (key not found, dimension not found, cache miss) in `README.md`; verify each code example runs as written

## 7. Cleanup (`cache-cleanup`)

- [x] 7.1 Implement `cleanup()` with eviction by idle time, the eviction setting that is off by default without an external cache, and the size estimate with eviction by memory limit; verify tests for every scenario of `specs/cache-cleanup/spec.md` except the interval helper, using a controllable clock
- [x] 7.2 Implement `start_cleanup()` as an `asyncio` task that the application can cancel; verify a test with a short interval that cleanup runs more than once and stops after cancellation
- [x] 7.3 Document cleanup settings and the interval helper in `README.md`; verify each code example runs as written

## 8. External cache (`external-cache`)

- [x] 8.1 Define the `Backend` protocol in `backends/base.py` and implement the in-process backend in `backends/memory.py`, with a method to drop entries and request counters for tests; verify a test that the in-process backend satisfies the protocol
- [x] 8.2 Connect `Store` to the backend: write new nodes in one set request, fetch missing values one level at a time, extend expiry on fetch, treat a partly missing value as a cache miss, and extend expiry during cleanup for values read since the previous cleanup; verify tests with the in-process backend for every scenario of `specs/external-cache/spec.md` that does not name Redis
- [x] 8.3 Implement the Redis backend in `backends/redis.py` with the key prefix, `SET` with expiry for nodes in a pipeline, `MGET` for fetches and `EXPIRE` in a pipeline; verify tests with `fakeredis` for the expiry scenarios and a test, skipped when `REDIS_URL` is not set, against a real Redis server
- [x] 8.4 Verify with a test in a subprocess without `redis` on the path that `import permafrost` succeeds
- [x] 8.5 Document configuring an external cache, the Redis backend, expiry times and writing a custom backend in `README.md`; verify each code example runs as written

## 9. Sharing dimensions between processes (`dimension-sharing`)

- [x] 9.1 Write the root hash after the nodes on every dimension change, with no expiry, and leave the dimension in memory unchanged when a backend call fails; verify tests for the write order, the failed write and the "Root hash entry in Redis" scenario
- [x] 9.2 Read a dimension not held in memory by fetching its root hash and whole key map, and raise dimension-not-found when the root hash or a key map node is missing; verify tests that use two `Store` objects sharing one in-process backend to stand for two processes
- [x] 9.3 Implement `reload()`; verify tests for "Pick up another process's change", "No reload" and "Two processes change the same dimension"
- [x] 9.4 Document sharing dimensions, `reload()` and "last write wins" in `README.md`; verify each code example runs as written

## 10. Integration checks

- [x] 10.1 Run an end-to-end test with two `Store` objects on `fakeredis`: store values on `main`, create `branch-a`, change one key, diff the branches, evict, read again, lose a node, and load it through the loader; verify the test passes
- [x] 10.2 Add a benchmark script under `benchmarks/` that reports the memory used by 1,000 dimensions created from one dimension of 10,000 keys and the time to create 10,000 model nodes; verify the script runs with `uv run python benchmarks/<name>.py` and prints both numbers
- [x] 10.3 Run `uv run pytest` and `openspec validate initial-version --strict`; verify both pass

## Workflow follow-up

- Archive the change with `/opsx:archive` after review.
