"""Redis backend unit tests using fakeredis."""

import subprocess
import sys

import fakeredis
import pytest

from permafrost import Backend, Store, hash_of
from permafrost.backends.redis import RedisBackend


@pytest.fixture
async def redis_backend():
    client = fakeredis.FakeAsyncRedis()
    yield RedisBackend(client, prefix="test:", node_ttl=24 * 3600)
    await client.aclose()


def _forget(store, collect):
    store._values.clear()
    store._read_at.clear()
    collect()


async def test_backend_implements_the_interface(redis_backend):
    assert isinstance(redis_backend, Backend)


async def test_expiry_set_on_write(redis_backend):
    store = Store(redis_backend)
    await store.create_dimension("main")
    await store.set("main", "k", {"redis-ttl": [1, 2]})
    ttl = await redis_backend.client.ttl(f"test:node:{hash_of({'redis-ttl': [1, 2]}).hex()}")
    assert 24 * 3600 - 10 <= ttl <= 24 * 3600


async def test_expiry_extended_on_read(redis_backend, collect):
    store = Store(redis_backend)
    await store.create_dimension("main")
    await store.set("main", "k", {"redis-touch": [3]})
    key = f"test:node:{hash_of({'redis-touch': [3]}).hex()}"
    await redis_backend.client.expire(key, 100)
    _forget(store, collect)
    assert await store.get("main", "k") == {"redis-touch": [3]}
    assert await redis_backend.client.ttl(key) > 100


async def test_root_hash_entry_has_no_expiry(redis_backend):
    store = Store(redis_backend)
    await store.create_dimension("main")
    await store.set("main", "k", 1)
    assert await redis_backend.client.ttl("test:dim:main") == -1
    assert await redis_backend.client.get("test:dim:main") == store.root_hash("main")


async def test_get_many_returns_none_for_missing_entries(redis_backend):
    await redis_backend.set_many({b"a" * 16: b"data"})
    assert await redis_backend.get_many([b"a" * 16, b"b" * 16]) == [b"data", None]
    assert await redis_backend.get_many([]) == []
    await redis_backend.set_many({})
    await redis_backend.touch([])


def test_from_url():
    backend = RedisBackend.from_url("redis://localhost:6379/0", prefix="x:", node_ttl=5)
    assert backend.prefix == "x:" and backend.node_ttl == 5


async def test_client_that_returns_strings():
    client = fakeredis.FakeAsyncRedis(decode_responses=True)
    backend = RedisBackend(client, prefix="test:")
    await client.set("test:dim:main", "abc")
    with pytest.raises(TypeError, match="decode_responses=False"):
        await backend.get_root("main")
    await client.aclose()


def test_import_without_the_redis_package():
    code = (
        "import sys; sys.modules['redis'] = None; "
        "import permafrost, permafrost.backends.redis; "
        "from permafrost import Store; Store(); print('ok')"
    )
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "ok"
