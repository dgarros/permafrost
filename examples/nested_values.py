"""Store a nested value, change it, and compare the versions.

The value is a dictionary with three children: a dictionary, a list and a set.

Run with: uv run python examples/nested_values.py
"""

from __future__ import annotations

import asyncio

from permafrost import (
    FrozenDict,
    FrozenList,
    FrozenSet,
    Store,
    diff,
    freeze,
    hash_of,
    merge,
    set_in,
)

device = {
    "hostname": "r1",
    "location": {"site": "paris", "rack": "A12"},
    "vlans": [10, 20],
    "tags": {"core", "edge"},
}


def read_only_values() -> None:
    print("== Read-only values")
    frozen = freeze(value=device)

    # Each child becomes the read-only form of its type.
    assert isinstance(frozen, FrozenDict)
    assert isinstance(frozen["location"], FrozenDict)
    assert isinstance(frozen["vlans"], FrozenList)
    assert isinstance(frozen["tags"], FrozenSet)
    print("location:", frozen["location"]["site"])
    print("vlans:", list(frozen["vlans"]))
    print("tags:", sorted(frozen["tags"]))

    # Every operation that would change a node raises an error.
    for description, change in (
        (
            "set a key of the dict",
            lambda: frozen["location"].__setitem__("site", "lyon"),
        ),
        ("append to the list", lambda: frozen["vlans"].append(30)),
        ("add to the set", lambda: frozen["tags"].add("access")),
    ):
        try:
            change()
        except (TypeError, AttributeError) as error:
            print(f"refused: {description} ({type(error).__name__})")

    # Equal content gives the same hash and the same object, whatever the order.
    other = freeze(
        value={
            "tags": {"edge", "core"},
            "vlans": [10, 20],
            "location": {"rack": "A12", "site": "paris"},
            "hostname": "r1",
        }
    )
    assert other is frozen
    print("hash:", hash_of(value=frozen).hex())


def changes_and_diff() -> None:
    print("\n== Changes and diff")
    before = freeze(value=device)

    # Change one value in each child. The previous version stays unchanged.
    after = set_in(value=before, path=("location", "rack"), new="B03")
    after = set_in(value=after, path=("vlans", 1), new=21)
    after = set_in(value=after, path=("tags",), new={"core", "access"})
    assert before["location"]["rack"] == "A12"

    # merge() adds the new list items at the end with lists="append".
    after = merge(value=after, partial={"vlans": [30]}, lists="append")
    print("after:", after["location"]["rack"], list(after["vlans"]), sorted(after["tags"]))

    # Children that did not change are the same object in both versions.
    unchanged = set_in(value=before, path=("hostname",), new="r1-paris")
    assert unchanged["location"] is before["location"]
    assert unchanged["vlans"] is before["vlans"]
    assert unchanged["tags"] is before["tags"]

    for entry in diff(a=before, b=after):
        print(f"{entry.kind:8} {entry.path}: {entry.old!r} -> {entry.new!r}")


async def dimensions() -> None:
    print("\n== Dimensions")
    store = Store()
    await store.create_dimension(name="main")
    await store.set(dimension="main", key="r1", value=device)

    # A new dimension holds the same keys and values, without copying them.
    await store.create_dimension(name="branch-a", source="main")
    await store.update(
        dimension="branch-a",
        key="r1",
        change=lambda value: set_in(value=value, path=("vlans", 0), new=11),
    )

    print("main vlans:", list((await store.get(dimension="main", key="r1"))["vlans"]))
    print(
        "branch-a vlans:",
        list((await store.get(dimension="branch-a", key="r1"))["vlans"]),
    )
    for change in await store.diff_keys(a="main", b="branch-a"):
        print("key", change)
    for entry in await store.diff(a="main", b="branch-a", key="r1"):
        print(f"{entry.kind:8} {entry.path}: {entry.old!r} -> {entry.new!r}")


if __name__ == "__main__":
    read_only_values()
    changes_and_diff()
    asyncio.run(main=dimensions())
