"""Redis lifecycle and isolated async clients for integration tests."""

from collections.abc import AsyncIterator, Iterator
from uuid import uuid4

import pytest
from redis.asyncio import Redis
from testcontainers.community.redis import RedisContainer

from permafrost.backends.redis import RedisBackend

REDIS_IMAGE = "redis:7.4.2-alpine"


@pytest.fixture(scope="session")
def redis_url() -> Iterator[str]:
    # RedisContainer waits for a successful Redis PING before yielding.
    with RedisContainer(REDIS_IMAGE) as container:
        host = container.get_container_host_ip()
        if ":" in host:
            host = f"[{host}]"
        yield f"redis://{host}:{container.get_exposed_port(6379)}/0"


@pytest.fixture
async def redis_backend(redis_url: str) -> AsyncIterator[RedisBackend[Redis]]:
    backend = RedisBackend.from_url(redis_url, prefix=f"permafrost-test-{uuid4().hex}:")
    try:
        yield backend
    finally:
        try:
            async for key in backend.client.scan_iter(match=f"{backend.prefix}*", count=100):
                await backend.client.delete(key)
        finally:
            await backend.client.aclose()


@pytest.fixture
async def redis_peer(redis_url: str, redis_backend: RedisBackend[Redis]) -> AsyncIterator[RedisBackend[Redis]]:
    backend = RedisBackend.from_url(redis_url, prefix=redis_backend.prefix)
    try:
        yield backend
    finally:
        await backend.client.aclose()
