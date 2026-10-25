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
from typing import Protocol


class NodeListener(Protocol):
    def node_created(self, h: bytes, node: object) -> None: ...


_nodes: weakref.WeakValueDictionary[bytes, object] = weakref.WeakValueDictionary()
_listeners: weakref.WeakSet[NodeListener] = weakref.WeakSet()


def _checked[T](h: bytes, node: object, cls: type[T]) -> T:
    # A hash identifies an encoding, and every encoding starts with the type
    # tag, so a node of another class under the same hash is a bug.
    if not isinstance(node, cls):
        raise TypeError(f"the node {h.hex()} is a {type(node).__qualname__}, not a {cls.__qualname__}")
    return node


def lookup[T](h: bytes, cls: type[T]) -> T | None:
    """Return the node held under this hash, which must be an instance of ``cls``, or ``None``."""
    node = _nodes.get(h)
    return None if node is None else _checked(h, node, cls)


def add[T](h: bytes, node: T, *, created: bool = True) -> T:
    """Add a node and return it, or return the node already held under this hash."""
    existing = _nodes.get(h)
    if existing is not None:
        return _checked(h, existing, type(node))
    _nodes[h] = node
    if created:
        for listener in _listeners:
            listener.node_created(h, node)
    return node


def add_listener(listener: NodeListener) -> None:
    _listeners.add(listener)


def remove_listener(listener: NodeListener) -> None:
    _listeners.discard(listener)


def items() -> list[tuple[bytes, object]]:
    return list(_nodes.items())


def size() -> int:
    """Return the number of nodes held in the process."""
    return len(_nodes)
