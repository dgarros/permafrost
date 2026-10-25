import weakref
from dataclasses import FrozenInstanceError

import pytest
from pydantic import ValidationError

from .models import Device, Interface


def test_pydantic_dataclass_with_base_class():
    d = Device(name="r1", interfaces=(Interface(name="eth0"),))
    assert not hasattr(d, "__dict__")
    assert weakref.ref(d)() is d
    with pytest.raises(FrozenInstanceError):
        d.name = "r2"  # ty: ignore[invalid-assignment]


def test_pydantic_dataclass_still_validates():
    with pytest.raises(ValidationError):
        Device(name=1)  # ty: ignore[invalid-argument-type]
