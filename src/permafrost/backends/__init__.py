"""External cache backends."""

from .base import Backend
from .memory import MemoryBackend

__all__ = ["Backend", "MemoryBackend"]
