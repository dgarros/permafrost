"""External cache backend for Redis, using the ``asyncio`` client of the ``redis`` package.

Install it with the ``redis`` extra: ``pip install permafrost[redis]``.
"""

from __future__ import annotations

import inspect
from collections.abc import Awaitable, Mapping, Sequence
from types import TracebackType
from typing import TYPE_CHECKING, Protocol, Self

if TYPE_CHECKING:
    from redis.asyncio import Redis

DEFAULT_NODE_TTL = 24 * 3600

# The ``redis`` package declares each command as returning ``X | Awaitable[X]``,
# because its synchronous and asynchronous clients share the declarations.
type _Reply[T] = T | Awaitable[T]


class _Pipeline(Protocol):
    """The commands of a ``redis.asyncio`` pipeline that the backend uses."""

    async def __aenter__(self) -> Self: ...
    async def __aexit__(
        self, exc_type: type[BaseException] | None, exc: BaseException | None, tb: TracebackType | None, /
    ) -> object: ...
    def set(self, name: str, value: bytes, ex: int | None = None) -> object: ...
    def expire(self, name: str, time: int) -> object: ...
    async def execute(self) -> list[object]: ...


class RedisClient(Protocol):
    """The commands of a ``redis.asyncio.Redis`` client that the backend uses."""

    def get(self, name: str) -> _Reply[bytes | str | None]: ...
    def mget(self, keys: list[str]) -> _Reply[list[bytes | str | None]]: ...
    def set(self, name: str, value: bytes) -> _Reply[bool | str | bytes | None]: ...
    def pipeline(self, transaction: bool = True) -> _Pipeline: ...
    async def aclose(self) -> None: ...


async def _result[T](reply: _Reply[T]) -> T:
    if inspect.isawaitable(reply):
        return await reply
    return reply


def _as_bytes(value: bytes | str | None) -> bytes | None:
    if isinstance(value, str):
        raise TypeError("the Redis client must return bytes: create it with decode_responses=False")
    return value


class RedisBackend[C: RedisClient]:
    """Stores each node as one Redis entry with an expiry time.

    Node entries are named ``<prefix>node:<hex hash>`` and dimension root
    hashes ``<prefix>dim:<name>``. The client must return bytes, which is the
    default (``decode_responses=False``).
    """

    def __init__(self, client: C, *, prefix: str = "permafrost:", node_ttl: int = DEFAULT_NODE_TTL) -> None:
        self.client = client
        self.prefix = prefix
        self.node_ttl = node_ttl

    @staticmethod
    def from_url(url: str, *, prefix: str = "permafrost:", node_ttl: int = DEFAULT_NODE_TTL) -> RedisBackend[Redis]:
        """Create a backend with a new client for ``url``."""
        from redis.asyncio import Redis

        return RedisBackend(Redis.from_url(url), prefix=prefix, node_ttl=node_ttl)

    def _node_key(self, h: bytes) -> str:
        return f"{self.prefix}node:{h.hex()}"

    def _dim_key(self, dimension: str) -> str:
        return f"{self.prefix}dim:{dimension}"

    async def get_many(self, hashes: Sequence[bytes]) -> list[bytes | None]:
        if not hashes:
            return []
        found = await _result(self.client.mget([self._node_key(h) for h in hashes]))
        return [_as_bytes(value) for value in found]

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
        return _as_bytes(await _result(self.client.get(self._dim_key(dimension))))

    async def set_root(self, dimension: str, root: bytes) -> None:
        await _result(self.client.set(self._dim_key(dimension), root))
