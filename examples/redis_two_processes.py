"""Share dimensions between two processes through Redis.

Process A stores devices in `main`, creates `branch-a` from it, changes one device and
sends the name of the new dimension to process B. Process B reads `branch-a` from Redis,
creates `branch-b` from it, changes it and sends that name back. Process A then reads
`branch-b` from Redis and compares it with `branch-a`.

Each process has its own memory, so a dimension that the other process created is read
from Redis: first its root hash, then its key map, then the values that are read.

Requires a Redis server. Set REDIS_URL to use another one than redis://localhost:6379/0.

Run with: uv run python examples/redis_two_processes.py
"""

from __future__ import annotations

import asyncio
import multiprocessing
import os
import sys
import uuid
from collections.abc import Mapping

from redis.exceptions import ConnectionError as RedisConnectionError

from permafrost import FrozenList, Store, set_in
from permafrost.backends.redis import RedisBackend

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

DEVICES = {
    "r1": {"site": "paris", "vlans": [10, 20], "tags": {"core"}},
    "r2": {"site": "paris", "vlans": [10], "tags": {"edge"}},
    "r3": {"site": "lyon", "vlans": [30], "tags": {"edge"}},
}


def log(process: str, message: str) -> None:
    print(f"[{process}] {message}", flush=True)


async def process_a(prefix: str, to_b: multiprocessing.Queue, from_b: multiprocessing.Queue) -> None:
    backend = RedisBackend.from_url(url=REDIS_URL, prefix=prefix)
    store = Store[Mapping[str, object]](backend=backend)

    await store.create_dimension(name="main")
    for name, device in DEVICES.items():
        await store.set(dimension="main", key=name, value=device)
    log(process="A", message=f"stored {len(DEVICES)} devices in main")

    # Creating a dimension writes only its root hash: it shares every node with main.
    await store.create_dimension(name="branch-a", source="main")
    await store.update(
        dimension="branch-a",
        key="r1",
        change=lambda device: set_in(value=device, path=("vlans",), new=[10, 20, 40]),
    )
    log(process="A", message="created branch-a from main and added VLAN 40 to r1")
    to_b.put(obj="branch-a")

    dimension = await asyncio.to_thread(from_b.get)
    log(process="A", message=f"received {dimension}")
    # Process A never held branch-b: it reads the dimension from Redis.
    for change in await store.diff_keys(a="branch-a", b=dimension):
        log(process="A", message=f"{change.kind:8} key {change.key}")
    for entry in await store.diff(a="branch-a", b=dimension, key="r2"):
        log(
            process="A",
            message=f"{entry.kind:8} r2 {entry.path}: {entry.old!r} -> {entry.new!r}",
        )

    await backend.client.aclose()


async def process_b(prefix: str, to_a: multiprocessing.Queue, from_a: multiprocessing.Queue) -> None:
    backend = RedisBackend.from_url(url=REDIS_URL, prefix=prefix)
    store = Store[Mapping[str, object]](backend=backend)

    dimension = await asyncio.to_thread(from_a.get)
    log(process="B", message=f"received {dimension}")
    # Process B never held main or branch-a: it reads both from Redis.
    for change in await store.diff_keys(a="main", b=dimension):
        log(process="B", message=f"{change.kind:8} key {change.key}")
    r1 = await store.get(dimension=dimension, key="r1")
    vlans = r1["vlans"]
    assert isinstance(vlans, FrozenList)
    log(process="B", message=f"r1 in {dimension} has VLANs {list(vlans)}")

    await store.create_dimension(name="branch-b", source=dimension)
    await store.update(
        dimension="branch-b",
        key="r2",
        change=lambda device: set_in(value=device, path=("tags",), new={"edge", "access"}),
    )
    await store.set(
        dimension="branch-b",
        key="r4",
        value={"site": "lyon", "vlans": [30], "tags": {"core"}},
    )
    await store.delete(dimension="branch-b", key="r3")
    log(
        process="B",
        message=f"created branch-b from {dimension}, changed r2, added r4 and deleted r3",
    )
    to_a.put(obj="branch-b")

    await backend.client.aclose()


def run_a(prefix: str, to_b: multiprocessing.Queue, from_b: multiprocessing.Queue) -> None:
    asyncio.run(main=process_a(prefix=prefix, to_b=to_b, from_b=from_b))


def run_b(prefix: str, to_a: multiprocessing.Queue, from_a: multiprocessing.Queue) -> None:
    asyncio.run(main=process_b(prefix=prefix, to_a=to_a, from_a=from_a))


async def check_redis() -> bool:
    backend = RedisBackend.from_url(url=REDIS_URL)
    try:
        await backend.client.ping()
        return True
    except RedisConnectionError:
        return False
    finally:
        await backend.client.aclose()


async def delete_entries(prefix: str) -> None:
    # Permafrost never deletes entries: Redis removes nodes when they expire.
    # The example deletes its own entries so that it leaves Redis as it found it.
    backend = RedisBackend.from_url(url=REDIS_URL)
    keys = [key async for key in backend.client.scan_iter(match=f"{prefix}*")]
    if keys:
        await backend.client.delete(*keys)
    await backend.client.aclose()


def main() -> None:
    if not asyncio.run(main=check_redis()):
        sys.exit(f"Cannot connect to Redis at {REDIS_URL}. Set REDIS_URL to a running server.")

    # A prefix for this run, so that the example does not read or change other data.
    prefix = f"permafrost-example-{uuid.uuid4().hex[:8]}:"
    context = multiprocessing.get_context(method="spawn")
    a_to_b = context.Queue()
    b_to_a = context.Queue()
    processes = [
        context.Process(target=run_a, kwargs={"prefix": prefix, "to_b": a_to_b, "from_b": b_to_a}),
        context.Process(target=run_b, kwargs={"prefix": prefix, "to_a": b_to_a, "from_a": a_to_b}),
    ]
    try:
        for process in processes:
            process.start()
        for process in processes:
            process.join(timeout=30)
    finally:
        asyncio.run(main=delete_entries(prefix=prefix))
    if any(process.exitcode != 0 for process in processes):
        sys.exit("A process failed.")


if __name__ == "__main__":
    main()
