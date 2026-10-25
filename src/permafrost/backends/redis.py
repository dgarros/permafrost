"""External cache backend for Redis, using the ``asyncio`` client of the ``redis`` package.

Install it with the ``redis`` extra: ``pip install permafrost[redis]``.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from redis.asyncio import Redis

DEFAULT_NODE_TTL = 24 * 3600


class RedisBackend:
    """Stores each node as one Redis entry with an expiry time.

    Node entries are named ``<prefix>node:<hex hash>`` and dimension root
    hashes ``<prefix>dim:<name>``. The client must return bytes, which is the
    default (``decode_responses=False``).
    """

    def __init__(self, client: Redis, *, prefix: str = "permafrost:", node_ttl: int = DEFAULT_NODE_TTL) -> None:
        self.client = client
        self.prefix = prefix
        self.node_ttl = node_ttl

    @classmethod
    def from_url(cls, url: str, **kwargs: Any) -> RedisBackend:
        """Create a backend with a new client for ``url``. Other arguments go to the backend."""
        from redis.asyncio import Redis

        return cls(Redis.from_url(url), **kwargs)

    def _node_key(self, h: bytes) -> str:
        return f"{self.prefix}node:{h.hex()}"

    def _dim_key(self, dimension: str) -> str:
        return f"{self.prefix}dim:{dimension}"

    async def get_many(self, hashes: Sequence[bytes]) -> list[bytes | None]:
        if not hashes:
            return []
        return await self.client.mget([self._node_key(h) for h in hashes])

    async def set_many(self, nodes: Mapping[bytes, bytes]) -> None:
        if not nodes:
            return
        async with self.client.pipeline(transaction=False) as pipe:
            for h, data in nodes.items():
                pipe.set(self._node_key(h), data, ex=self.node_ttl)
            await pipe.execute()

    async def touch(self, hashes: Sequence[bytes]) -> None:
        if not hashes:
            return
        async with self.client.pipeline(transaction=False) as pipe:
            for h in hashes:
                pipe.expire(self._node_key(h), self.node_ttl)
            await pipe.execute()

    async def get_root(self, dimension: str) -> bytes | None:
        return await self.client.get(self._dim_key(dimension))

    async def set_root(self, dimension: str, root: bytes) -> None:
        await self.client.set(self._dim_key(dimension), root)
