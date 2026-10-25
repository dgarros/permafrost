# Design

## Context

The repository holds no implementation: `src/permafrost/__init__.py` contains a placeholder `hello()` function, and the only dependency is `pydantic>=2.12.4`. `SPEC.md` describes the architecture (nodes, registry, key map, dimensions, external cache, loader, cleanup) and records memory measurements that drive several decisions below. See `proposal.md` for the reasons for the change and the specs under `specs/` for the required behavior. This document covers the decisions that `SPEC.md` leaves open.

## Goals / Non-Goals

**Goals:**

- A public API small enough to describe in one page, with `async` operations only where a read can reach the external cache or the loader.
- Node classes that use as little memory as `SPEC.md` measures for slotted classes, and support weak references.
- One serialization of each node, used both for its hash and for its external cache entry.
- A test suite that runs without a Redis server.

**Non-Goals:**

- Performance tuning beyond the choices below. Benchmarks are a task, but there are no targets yet, because `SPEC.md` lists the memory targets as an open question.
- Thread safety, persistence, and the other items in the "Out of scope" section of `SPEC.md`.
- Incremental list update during a merge.

## Decisions

### Module layout

```
src/permafrost/
  __init__.py      public API
  errors.py        error classes
  nodes.py         FrozenDict, FrozenList, FrozenTuple, FrozenSet, FrozenModel base class
  codec.py         deterministic msgpack encoding, hashing, decoding
  types.py         freeze(): input value → node tree; type handler registry
  registry.py      weak registry hash → node
  ops.py           set_in, delete_in, merge
  diff.py          diff of two values
  keymap.py        hash array mapped trie of key → value hash
  store.py         Store: dimensions, value cache, loader, cleanup
  backends/
    base.py        Backend protocol
    memory.py      in-process backend for tests and development
    redis.py       Redis backend
```

### Read-only collection classes wrap built-in containers

`FrozenDict`, `FrozenList`, `FrozenTuple` and `FrozenSet` are classes with `__slots__ = ("_data", "_hash", "__weakref__")`. `_data` holds a `dict`, `tuple` or `frozenset`. They implement `collections.abc.Mapping`, `Sequence` and `Set`, and compare equal to built-in values with the same content.

- Alternative: subclass `dict` or `list` and override the methods that change content. Rejected because C code and `dict.__setitem__(obj, ...)` bypass the overrides, so the data would not be read-only.
- Alternative: subclass `tuple` for lists. Rejected because Python does not allow non-empty `__slots__` on a `tuple` subclass, so each instance would get a `__dict__`.

`FrozenList` and `FrozenTuple` are separate classes so that `[1, 2]` and `(1, 2)` have different hashes and are returned as the type that was stored.

### Where each node keeps its hash

- Permafrost collection classes: in the `_hash` slot.
- Pydantic dataclasses: the base class `FrozenModel` declares `__slots__ = ("__weakref__", "_pf_hash")`. User classes inherit from it. The dataclass `__eq__` compares fields only, so the extra slot does not change equality.
- Pydantic models (`BaseModel`): a side table `dict[int, bytes]` keyed by `id()`, with a `weakref.finalize` callback that removes the entry. Writing the hash into the instance `__dict__` was rejected, because `BaseModel.__eq__` compares `__dict__`.

### Freezing a value

`freeze()` walks the input from the leaves up. For each container it freezes the children, encodes the node, hashes the bytes, and looks up the hash in the registry. When the registry already holds the hash, `freeze()` returns the existing node and drops the new one. This is how identical nodes are held once.

- Models are created with `object.__new__` and `object.__setattr__`, as measured in `SPEC.md`. Pydantic validation and `__post_init__` do not run.
- Field values of models are frozen too. A field typed `list[str]` therefore holds a `FrozenList`. Type checkers do not see this difference. The documentation states it.
- Input that is already a node, such as a value returned by the library, is returned as it is, without encoding.
- Scalars are kept inside their parent node. A value that is only a scalar is wrapped in no node: its hash is the hash of its encoding, and the value cache holds it as it is.

### Encoding and hashing

Each node is encoded with msgpack (`use_bin_type=True`) as `[tag, payload]`.

- Tags identify the node type: dictionary, list, tuple, set, Pydantic dataclass, Pydantic model, and each registered type handler.
- A child node is written as a msgpack extension type that holds its 16-byte hash. Scalars are written inline. `date` and `datetime` use their own extension types.
- Dictionary entries are sorted by the encoded bytes of the key. Set items are sorted by their encoded bytes. Sorting by bytes works for keys of mixed types, which Python cannot sort directly.
- Model fields are written in the order the class declares them, after the class path `module:qualname`.
- The hash is `hashlib.blake2b(data, digest_size=16).digest()`.

A node read from the external cache is rebuilt from these bytes. Model classes are found by importing the class path, or from a mapping the application passes, for classes that cannot be imported by path.

### Type handlers

A type handler registers a Python type, a tag name, an `encode` function that returns a supported value, and a `decode` function that returns a read-only instance of the type from the frozen encoded value. The library stores a node that holds the frozen encoded value and the decoded instance, and returns the decoded instance. The library does not check that `decode` returns a read-only object. The documentation states that this is the handler's responsibility.

### Registry

`weakref.WeakValueDictionary[bytes, node]`, as `SPEC.md` describes. `SPEC.md` measures 189 bytes for each entry. Switching to a plain `dict` with garbage collection during cleanup stays possible later, because only `registry.py` depends on this choice.

### Key map

A hash array mapped trie with 32-way branching.

- The position of a key is given by successive 5-bit groups of `blake2b(key, digest_size=16)`.
- A branch node holds a 32-bit bitmap and a tuple of children. A child is a branch node or a leaf.
- A leaf holds the key and the hash of its value root. A collision node holds several leaves, sorted by key, for keys whose 128-bit hashes are equal.
- Canonical shape: a leaf sits at the shallowest level where no other key shares its prefix. After a delete, a branch that holds a single leaf and no branch is replaced by that leaf in its parent. These rules make the shape depend only on the set of keys.
- Key map nodes refer to child key map nodes by direct reference, and to values by hash only.
- Keys are strings. `SPEC.md` does not set the type of a key. Strings cover branch-based use and keep the key hash simple. Other key types can be added later without changing the stored format of string keys.

### Store and public API

One `Store` object holds the registry, the dimensions, the value cache, the backend, the loader and the cleanup settings.

```python
store = Store(backend=None, loader=None, idle_time=3600, eviction=None, memory_limit=None)

await store.create_dimension("branch-a", source="main")
await store.set("main", "device-1", value)
value = await store.get("main", "device-1")
await store.delete("main", "device-1")
await store.update("main", "device-1", lambda v: merge(v, {"name": "r2"}))
keys = await store.keys("main")
changes = await store.diff_keys("main", "branch-a")
entries = await store.diff("main", "branch-a", "device-1")
await store.reload("main")
store.root_hash("main")
store.cleanup()
task = store.start_cleanup(interval=60)

frozen = freeze(value)
set_in(frozen, ("a", "b"), 2)
delete_in(frozen, ("a",))
merge(frozen, partial, lists="replace")
diff(a, b)
hash_of(a)
```

- Writes are `async` because they write to the external cache.
- The default list behavior of `merge()` is "replace". `SPEC.md` does not set a default. "Replace" is the behavior that keeps the result free of the existing list, which is the least surprising for a merge of configuration data. The "append" behavior is the rule selected for this change.

### Order of writes and failures

A write to a dimension creates the new nodes, sends them to the backend, sends the new root hash, and only then switches the dimension in memory to the new root. When a backend call raises an error, the dimension in memory is unchanged and the error reaches the caller.

Each dimension has an `asyncio.Lock`. Two tasks in the same process that write the same dimension run one after the other, so neither replaces the other's change. Changes from other processes are still "last write wins", as `SPEC.md` describes.

### Reading a dimension from the external cache

When a process reads a dimension it does not hold, it reads the root hash and fetches the whole key map, one level at a time. For 10,000 keys this is 3 or 4 requests. Fetching only the key map nodes on the path to one key was rejected because it would need key map nodes that change from "not fetched" to "fetched", which conflicts with nodes being read-only. When any key map node is missing, the read raises the dimension-not-found error.

### Which nodes a write sends

A store with a backend registers with the registry and is told about each node that Permafrost creates, as opposed to nodes rebuilt from the external cache. It keeps these nodes in a weak dictionary of nodes to send. A write walks the new value and key map from their roots, sends the nodes that are in this dictionary, and does not go below a node that is not in it. When the store is created, every node already in the registry is added to the dictionary.

A value returned by the loader is sent with every node, not only the new ones. The external cache lost at least one node of that value, and this process can still hold that node in memory from before, so it would not count as new.

### Value cache and read times

The value cache is a `dict` from value hash to value root, with the time of the last read or write in a second `dict`, kept in least-recently-read order. `SPEC.md` goal 11 says the read time is recorded on the root node of the value, while the architecture section says the value cache holds it. Keeping it in the value cache avoids a slot on every node class, including user model classes and plain scalars that are value roots. `SPEC.md` is updated to say the value cache records the read time.

Reading a key looks up the value hash in the value cache, then in the registry (the value can still be alive because another value or the user holds it), then in the external cache, then calls the loader.

### Memory estimate for the memory limit

Each value root gets a size estimate when it enters the value cache: the sum of `sys.getsizeof` of its nodes and their direct data. A node shared by two values counts in both. The estimate is therefore higher than the real memory use, which makes the limit stricter than it needs to be, never looser.

### Expiry in the external cache

- Node entries: `SET` with `EX` set to the configured expiry time (24 hours by default), in one pipeline for each write.
- When the library fetches nodes, it extends their expiry time with one pipeline of `EXPIRE` commands.
- Values read only from memory do not touch Redis on every read. Instead, cleanup extends the expiry time of the values in the value cache that were read since the previous cleanup. Without this, a value that stays in the memory of one process could expire in Redis, and other processes would have to call the loader.
- Cleanup also extends the expiry time of every key map node of the dimensions held in memory. Key map nodes have an expiry time like other nodes, and a dimension that nobody changes for 24 hours would otherwise lose its key map in Redis, so other processes would get `DimensionNotFoundError`.
- Dimension root hashes: `SET` with no expiry.
- Redis keys use a configurable prefix: `<prefix>node:<hex hash>` and `<prefix>dim:<name>`.

### Dependencies and tests

- Runtime: `msgpack`. Optional group `redis`: `redis>=5`.
- Development: `pytest-asyncio` and `fakeredis`, so that the Redis backend tests run without a Redis server. A test marked `redis` runs against a real server when `REDIS_URL` is set.
- Most tests for the external cache use the in-process backend from `backends/memory.py`, which can drop entries on request to simulate a cache that loses data.

## Risks / Trade-offs

- [Python considers `1`, `1.0` and `True` equal, but their encodings differ, so `{1: "a"}` and `{True: "a"}` get different hashes.] → Document it. Equal hashes still always mean equal content.
- [Model fields hold `FrozenList` where the class declares `list`, which type checkers do not report.] → Document it, and recommend `tuple[...]` fields in user models.
- [Fetching a value one level at a time takes as many requests as the value is deep.] → `SPEC.md` keeps this as an open question. The backend interface takes a list of hashes, so a later change can fetch several levels at once without changing the interface.
- [Rebuilding a model from the external cache imports its class by path, so a renamed or moved class cannot be read.] → The application can pass a mapping of class paths. A read that cannot find the class is a cache miss and calls the loader.
- [Weak references add about 105 bytes for each node compared with strong references, as measured in `SPEC.md`.] → Accepted for this change. The registry is isolated in `registry.py` so that it can switch later.
- [Fetching the whole key map of a dimension uses memory for dimensions that a process reads only one key from.] → For 10,000 keys this is a few hundred kilobytes, and the key map nodes are shared with every other dimension in the process.

## Migration Plan

None. There is no previous version or user.

## Open Questions

- The default expiry time in Redis (24 hours) and the default idle time in memory (60 minutes) come from examples in `SPEC.md`. They are settings and can change without changing the design.
