import gc

import pytest


@pytest.fixture
def collect():
    """Return a function that runs the garbage collector, for tests that check what Python frees."""

    def run() -> None:
        gc.collect()

    return run
