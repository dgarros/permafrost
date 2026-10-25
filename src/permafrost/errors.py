"""Errors raised by Permafrost."""

from __future__ import annotations


class PermafrostError(Exception):
    """Base class of every error that Permafrost raises."""


class ReadOnlyError(PermafrostError, TypeError):
    """Raised when code tries to change a stored value."""


class UnsupportedTypeError(PermafrostError, TypeError):
    """Raised when a value contains a type that Permafrost cannot store."""


class PathError(PermafrostError, LookupError):
    """Raised when a path does not exist in a value or cannot be updated."""


class KeyNotFoundError(PermafrostError, LookupError):
    """Raised when a dimension does not hold a key."""

    def __init__(self, dimension: str, key: str) -> None:
        super().__init__(f"key {key!r} not found in dimension {dimension!r}")
        self.dimension = dimension
        self.key = key


class DimensionNotFoundError(PermafrostError, LookupError):
    """Raised when a dimension is neither in memory nor in the external cache."""

    def __init__(self, dimension: str, reason: str = "not found") -> None:
        super().__init__(f"dimension {dimension!r} {reason}")
        self.dimension = dimension


class DimensionExistsError(PermafrostError):
    """Raised when creating a dimension with a name that already exists."""

    def __init__(self, dimension: str) -> None:
        super().__init__(f"dimension {dimension!r} already exists")
        self.dimension = dimension


class CacheMissError(PermafrostError, LookupError):
    """Raised when a value is in no cache and no loader is registered."""

    def __init__(self, dimension: str, key: str) -> None:
        super().__init__(f"value of key {key!r} in dimension {dimension!r} is in no cache and no loader is registered")
        self.dimension = dimension
        self.key = key
