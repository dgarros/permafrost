"""Simulate separate processes that share one external cache.

Each ``Process`` has its own registry of nodes, so a store used inside
``with process:`` cannot find nodes that another process created, and has to
fetch them from the external cache.
"""

from __future__ import annotations

import weakref
from typing import Self

from permafrost import keymap, registry
from permafrost.registry import NodeListener


class Process:
    def __init__(self) -> None:
        self.nodes: weakref.WeakValueDictionary[bytes, object] = weakref.WeakValueDictionary()
        self.listeners: weakref.WeakSet[NodeListener] = weakref.WeakSet()
        # Importing permafrost puts the empty key map in the registry of every process.
        self.nodes[keymap.EMPTY._pf_hash] = keymap.EMPTY
        self._saved: list[tuple[weakref.WeakValueDictionary[bytes, object], weakref.WeakSet[NodeListener]]] = []

    def __enter__(self) -> Self:
        self._saved.append((registry._nodes, registry._listeners))
        registry._nodes = self.nodes
        registry._listeners = self.listeners
        return self

    def __exit__(self, *exc: object) -> None:
        registry._nodes, registry._listeners = self._saved.pop()
