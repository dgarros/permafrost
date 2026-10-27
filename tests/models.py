"""Model classes shared by the tests. They live in a module so they can be imported by path."""

from __future__ import annotations

from enum import Enum, IntEnum, IntFlag, StrEnum

from pydantic import BaseModel, ConfigDict
from pydantic.dataclasses import dataclass

from permafrost import FrozenModel

POST_INIT_CALLS = []


class State(str, Enum):
    PRESENT = "present"
    ABSENT = "absent"


class OtherState(str, Enum):
    PRESENT = "present"


class Color(StrEnum):
    RED = "red"


class Level(IntEnum):
    LOW = 1
    HIGH = 2
    HUGE = 2**70


class Perm(IntFlag):
    R = 4
    W = 2
    X = 1


@dataclass(frozen=True, slots=True)
class Interface(FrozenModel):
    name: str
    vlans: tuple[int, ...] = ()


@dataclass(frozen=True, slots=True)
class Device(FrozenModel):
    name: str
    site: str = "paris"
    interfaces: tuple[Interface, ...] = ()
    tags: list[str] | None = None

    def __post_init__(self) -> None:
        POST_INIT_CALLS.append(self.name)


class Site(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    devices: list[str] = []


class Item(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    state: State = State.PRESENT
