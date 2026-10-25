# Examples

Each example is a script that prints what it does. Run an example from the repository root with `uv run python examples/<name>.py`. `tests/test_examples.py` runs every example.

## `nested_values.py`

Stores a device as a dictionary with three children: a `location` dictionary, a `vlans` list and a `tags` set.

- Freezes the value and shows that each child becomes a `FrozenDict`, `FrozenList` or `FrozenSet` that refuses changes.
- Shows that the same content in a different order gives the same hash and the same object.
- Changes one value in each child with `set_in()` and `merge()`, and prints the result of `diff()`. Unchanged children are the same object in both versions.
- Stores the device in the dimension `main`, creates `branch-a` from it, changes a VLAN in `branch-a`, and compares the two dimensions.

## `pydantic_models.py`

Stores a site as a Pydantic model (`BaseModel`) that holds devices, which are Pydantic dataclasses that inherit from `FrozenModel` and hold interfaces.

- Shows that Pydantic validates data when the application creates a model, and that frozen models refuse changes to their fields.
- Shows that two interfaces with the same content are the same object, and that a field declared as `list` holds a `FrozenList`.
- Changes fields through a path of field names and tuple indexes with `set_in()` and `merge()`, and prints the result of `diff()`. `set_in()` refuses a field that the model class does not declare.
- Stores each device under its name in `main`, changes one device in `branch-a`, and compares the two dimensions.

Permafrost does not run Pydantic validation when it changes a model. The example uses a store without an external cache: with an external cache, model classes defined in a script would need `register_class()`, because another process cannot import them by path.

## `redis_two_processes.py`

Starts two processes that share dimensions through Redis. Each process has its own memory, so it reads a dimension that the other process created from Redis.

1. Process A stores three devices in `main`, creates `branch-a` from it, changes one device, and sends the name `branch-a` to process B.
2. Process B reads `main` and `branch-a` from Redis, compares them, creates `branch-b` from `branch-a`, changes, adds and deletes devices, and sends the name `branch-b` to process A.
3. Process A reads `branch-b` from Redis and compares it with `branch-a`.

This example requires a Redis server. It uses `redis://localhost:6379/0` unless `REDIS_URL` is set, and `tests/test_examples.py` skips it when `REDIS_URL` is not set. For example, with Docker:

```shell
docker run -d --rm --name permafrost-redis -p 6379:6379 redis:7-alpine
uv run python examples/redis_two_processes.py
docker stop permafrost-redis
```

Each run writes its entries under its own key prefix, such as `permafrost-example-1a2b3c4d:`, and deletes them at the end. Permafrost itself never deletes entries: Redis removes nodes when they expire.
