"""Registry of nodes by hash.

The registry holds weak references, so it finds an existing node by hash
without keeping it in memory. A node disappears from the registry when Python
frees it.

Objects registered with ``add_listener`` are told about each node that
Permafrost creates, as opposed to nodes rebuilt from the external cache. A
store uses this to know which nodes it still has to write to its external
cache.
"""

from __future__ import annotations

import weakref
from typing import Any, Protocol


class NodeListener(Protocol):
    def node_created(self, h: bytes, node: Any) -> None: ...


_nodes: weakref.WeakValueDictionary[bytes, Any] = weakref.WeakValueDictionary()
_listeners: weakref.WeakSet[Any] = weakref.WeakSet()


def lookup(h: bytes) -> Any | None:
    return _nodes.get(h)


def add(h: bytes, node: Any, *, created: bool = True) -> Any:
    """Add a node and return it, or return the node already held under this hash."""
    existing = _nodes.get(h)
    if existing is not None:
        return existing
    _nodes[h] = node
    if created:
        for listener in _listeners:
            listener.node_created(h, node)
    return node


def add_listener(listener: NodeListener) -> None:
    _listeners.add(listener)


def remove_listener(listener: NodeListener) -> None:
    _listeners.discard(listener)


def items() -> list[tuple[bytes, Any]]:
    return list(_nodes.items())


def size() -> int:
    """Return the number of nodes held in the process."""
    return len(_nodes)
