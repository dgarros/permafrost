"""Measure the memory used by many dimensions and the time to create model nodes.

Run with: uv run python benchmarks/dimensions.py
"""

from __future__ import annotations

import asyncio
import time
import tracemalloc

from pydantic.dataclasses import dataclass

from permafrost import FrozenModel, Store, freeze, registry


@dataclass(frozen=True, slots=True)
class Device(FrozenModel):
    name: str
    serial: int
    active: bool
    tags: tuple[str, ...]


KEYS = 10_000
DIMENSIONS = 1_000
MODELS = 10_000


async def measure_dimensions() -> None:
    store = Store()
    await store.create_dimension("main")
    for i in range(KEYS):
        await store.set("main", f"device-{i}", Device(name=f"device-{i}", serial=i, active=True, tags=("core",)))

    nodes_before = registry.size()
    tracemalloc.start()
    start = tracemalloc.take_snapshot()
    began = time.perf_counter()
    for i in range(DIMENSIONS):
        await store.create_dimension(f"branch-{i}", source="main")
    elapsed = time.perf_counter() - began
    end = tracemalloc.take_snapshot()
    tracemalloc.stop()
    used = sum(stat.size_diff for stat in end.compare_to(start, "filename"))

    print(f"{DIMENSIONS} dimensions created from one dimension of {KEYS} keys:")
    print(f"  memory used: {used / 1024:.1f} KiB ({used / DIMENSIONS:.0f} bytes per dimension)")
    print(f"  time: {elapsed * 1000:.1f} ms")
    print(f"  new nodes in the registry: {registry.size() - nodes_before}")

    began = time.perf_counter()
    for i in range(DIMENSIONS):
        await store.set(f"branch-{i}", f"device-{i}", Device(name=f"changed-{i}", serial=i, active=False, tags=()))
    elapsed = time.perf_counter() - began
    print(f"  then one key changed in each dimension: {elapsed * 1000:.1f} ms")
    print(f"  nodes in the registry after the changes: {registry.size() - nodes_before} more than before")


def measure_models() -> None:
    values = [Device(name=f"model-{i}", serial=i, active=True, tags=("a", "b")) for i in range(MODELS)]
    began = time.perf_counter()
    for value in values:
        freeze(value)
    elapsed = time.perf_counter() - began
    print(f"{MODELS} model nodes created with freeze(): {elapsed / MODELS * 1e9:.0f} ns per node")


if __name__ == "__main__":
    asyncio.run(measure_dimensions())
    measure_models()
