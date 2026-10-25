"""External cache backend that keeps entries in the current process.

Use it for development and tests: several stores can share one instance to
stand for several processes that share one external cache.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence


class MemoryBackend:
    """In-process backend. It counts requests and can drop entries on request."""

    def __init__(self) -> None:
        self.nodes: dict[bytes, bytes] = {}
        self.roots: dict[str, bytes] = {}
        self.get_requests = 0
        self.set_requests = 0
        self.touch_requests = 0
        self.requested: list[bytes] = []
        self.last_set: list[bytes] = []
        self.touched: list[bytes] = []
        self.log: list[str] = []

    async def get_many(self, hashes: Sequence[bytes]) -> list[bytes | None]:
        self.get_requests += 1
        self.log.append("get_many")
        self.requested.extend(hashes)
        return [self.nodes.get(h) for h in hashes]

    async def set_many(self, nodes: Mapping[bytes, bytes]) -> None:
        self.set_requests += 1
        self.log.append("set_many")
        self.last_set = list(nodes)
        self.nodes.update(nodes)

    async def touch(self, hashes: Sequence[bytes]) -> None:
        self.touch_requests += 1
        self.log.append("touch")
        self.touched.extend(hashes)

    async def get_root(self, dimension: str) -> bytes | None:
        return self.roots.get(dimension)

    async def set_root(self, dimension: str, root: bytes) -> None:
        self.log.append("set_root")
        self.roots[dimension] = root

    def drop(self, hashes: Iterable[bytes]) -> None:
        """Remove node entries, as an external cache that loses data would."""
        for h in hashes:
            self.nodes.pop(h, None)

    def clear(self) -> None:
        """Remove every node entry and root hash, as after a restart."""
        self.nodes.clear()
        self.roots.clear()
