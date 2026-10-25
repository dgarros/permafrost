"""End-to-end check across every capability, with two processes sharing fakeredis."""

import fakeredis

from permafrost import DiffEntry, KeyChange, Store, hash_of, merge, set_in
from permafrost.backends.redis import RedisBackend

from .models import Device, Interface
from .process import Process


class Clock:
    now = 0.0

    def __call__(self):
        return self.now


async def test_end_to_end(collect):
    client = fakeredis.FakeAsyncRedis()
    backend = RedisBackend(client, prefix="e2e:")
    clock = Clock()
    database = {}

    async def loader(dimension, key):
        return database[(dimension, key)]

    a, b = Process(), Process()

    # Process A stores values on main.
    with a:
        store_a = Store(backend, loader, clock=clock, idle_time=60)
        await store_a.create_dimension("main")
        for i in range(50):
            device = Device(name=f"r{i}", interfaces=(Interface(name="eth0", vlans=(10, 20)),))
            database[("main", f"r{i}")] = device
            await store_a.set("main", f"r{i}", device)

        # Create a branch and change one key on it.
        await store_a.create_dimension("branch-a", source="main")
        changed = await store_a.update("branch-a", "r7", lambda d: set_in(d, ("interfaces", 0, "vlans"), (10, 20, 30)))
        database[("branch-a", "r7")] = changed
        await store_a.update("branch-a", "r8", lambda d: merge(d, {"site": "lyon"}))
        database[("branch-a", "r8")] = await store_a.get("branch-a", "r8")

        assert await store_a.diff_keys("main", "branch-a") == [KeyChange("r7", "changed"), KeyChange("r8", "changed")]
        assert await store_a.diff("main", "branch-a", "r7") == [
            DiffEntry(("interfaces", 0, "vlans", 2), "added", None, 30)
        ]

    # Process B reads the branch from Redis.
    with b:
        store_b = Store(backend, loader, clock=clock, idle_time=60)
        r7 = await store_b.get("branch-a", "r7")
        assert type(r7) is Device and r7.interfaces[0].vlans == (10, 20, 30)
        assert await store_b.diff_keys("main", "branch-a") == [KeyChange("r7", "changed"), KeyChange("r8", "changed")]
        assert store_b.root_hash("branch-a") == store_a.root_hash("branch-a")

        # Evict, then read again from Redis.
        clock.now += 61
        assert await store_b.cleanup() >= 1
        del r7
        collect()
        r7 = await store_b.get("branch-a", "r7")
        assert r7.interfaces[0].vlans == (10, 20, 30)

        # Redis loses a node: the read calls the loader.
        lost = hash_of(r7.interfaces)
        await client.delete(f"e2e:node:{lost.hex()}")
        clock.now += 61
        await store_b.cleanup()
        del r7
        collect()
        r7 = await store_b.get("branch-a", "r7")
        assert r7 == database[("branch-a", "r7")]
        # The loaded nodes were written back to Redis.
        assert await client.exists(f"e2e:node:{lost.hex()}")

    # Process A picks up nothing new, because nothing changed the root hashes.
    with a:
        before = store_a.root_hash("branch-a")
        await store_a.reload("branch-a")
        assert store_a.root_hash("branch-a") == before

    await client.aclose()
