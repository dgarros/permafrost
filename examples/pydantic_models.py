"""Store Pydantic models, change them, and compare the versions.

A site is a Pydantic model (`BaseModel`) that holds devices. A device is a Pydantic
dataclass that inherits from `FrozenModel` and holds interfaces.

Run with: uv run python examples/pydantic_models.py
"""

from __future__ import annotations

import asyncio

from pydantic import BaseModel, ConfigDict, ValidationError
from pydantic.dataclasses import dataclass

from permafrost import (
    FrozenModel,
    PathError,
    Store,
    diff,
    freeze,
    hash_of,
    merge,
    set_in,
)


@dataclass(frozen=True, slots=True)
class Interface(FrozenModel):
    name: str
    vlans: tuple[int, ...] = ()
    enabled: bool = True


@dataclass(frozen=True, slots=True)
class Device(FrozenModel):
    name: str
    role: str
    interfaces: tuple[Interface, ...] = ()


class Site(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    devices: tuple[Device, ...] = ()
    contacts: list[str] = []


def build_site() -> Site:
    # Pydantic validates the data here, when the application calls the classes.
    return Site(
        name="paris",
        devices=(
            Device(
                name="r1",
                role="core",
                interfaces=(
                    Interface(name="eth0", vlans=(10, 20)),
                    Interface(name="eth1"),
                ),
            ),
            Device(
                name="r2",
                role="edge",
                interfaces=(Interface(name="eth0", vlans=(10,)),),
            ),
        ),
        contacts=["noc@example.com"],
    )


def read_only_models() -> None:
    print("== Read-only models")
    try:
        Interface(name="eth0", vlans=("not-a-vlan",))
    except ValidationError:
        print("refused by Pydantic: a VLAN that is not an integer")

    site = freeze(value=build_site())
    assert type(site) is Site
    assert type(site.devices[0]) is Device
    print("devices:", [device.name for device in site.devices])

    # Model instances are read-only.
    try:
        site.devices[0].interfaces[0].enabled = False
    except AttributeError as error:
        print(f"refused: change a field ({type(error).__name__})")

    # Models with the same content are stored once.
    assert freeze(value=Interface(name="eth1")) is site.devices[0].interfaces[1]
    # The "eth0" interfaces of r1 and r2 have different VLANs, so they are two nodes.
    assert site.devices[0].interfaces[0] is not site.devices[1].interfaces[0]
    print("hash of the site:", hash_of(value=site).hex())

    # A field declared as `list` holds a read-only list after freeze().
    print("contacts type:", type(site.contacts).__name__)


def changes_and_diff() -> None:
    print("\n== Changes and diff")
    before = freeze(value=build_site())

    # A path goes through model fields and tuple indexes.
    after = set_in(value=before, path=("devices", 0, "interfaces", 1, "enabled"), new=False)

    # merge() merges a partial value field by field.
    after = merge(value=after, partial={"contacts": ["oncall@example.com"]}, lists="append")
    after = set_in(
        value=after,
        path=("devices", 1),
        new=merge(value=after.devices[1], partial={"role": "access"}),
    )

    # Neither set_in() nor merge() runs Pydantic validation, so the fields must exist.
    try:
        set_in(value=before, path=("devices", 0, "vendor"), new="acme")
    except PathError:
        print("refused: a field that the Device class does not have")

    # The interfaces of r1 that did not change are the same objects.
    assert after.devices[0].interfaces[0] is before.devices[0].interfaces[0]

    for entry in diff(a=before, b=after):
        print(f"{entry.kind:8} {entry.path}: {entry.old!r} -> {entry.new!r}")


async def dimensions() -> None:
    print("\n== Dimensions")
    store = Store()
    await store.create_dimension(name="main")
    site = build_site()
    for device in site.devices:
        await store.set(dimension="main", key=device.name, value=device)

    await store.create_dimension(name="branch-a", source="main")
    await store.update(
        dimension="branch-a",
        key="r2",
        change=lambda device: set_in(value=device, path=("interfaces", 0, "vlans"), new=(10, 30)),
    )

    print(
        "main r2 vlans:",
        tuple((await store.get(dimension="main", key="r2")).interfaces[0].vlans),
    )
    print(
        "branch-a r2 vlans:",
        tuple((await store.get(dimension="branch-a", key="r2")).interfaces[0].vlans),
    )
    for change in await store.diff_keys(a="main", b="branch-a"):
        print("key", change)
    for entry in await store.diff(a="main", b="branch-a", key="r2"):
        print(f"{entry.kind:8} {entry.path}: {entry.old!r} -> {entry.new!r}")


if __name__ == "__main__":
    read_only_models()
    changes_and_diff()
    asyncio.run(main=dimensions())
