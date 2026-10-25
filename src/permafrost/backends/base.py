"""Interface of an external cache backend."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Protocol, runtime_checkable


@runtime_checkable
class Backend(Protocol):
    """A cache service outside the process that holds nodes by hash.

    The backend can lose any entry at any time. It sets the expiry time of
    node entries itself. Dimension root hashes never expire by idle time.
    """

    async def get_many(self, hashes: Sequence[bytes]) -> list[bytes | None]:
        """Return the encoded node for each hash, or ``None`` when the backend does not hold it."""
        ...

    async def set_many(self, nodes: Mapping[bytes, bytes]) -> None:
        """Store encoded nodes by hash, in one request, with the node expiry time."""
        ...

    async def touch(self, hashes: Sequence[bytes]) -> None:
        """Extend the expiry time of the nodes with these hashes."""
        ...

    async def get_root(self, dimension: str) -> bytes | None:
        """Return the root hash of a dimension, or ``None``."""
        ...

    async def set_root(self, dimension: str, root: bytes) -> None:
        """Store the root hash of a dimension, with no expiry time."""
        ...
