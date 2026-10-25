"""Run each script of the examples directory."""

import os
import subprocess
import sys
from pathlib import Path

import pytest

EXAMPLES = sorted((Path(__file__).parent.parent / "examples").glob("*.py"))
NEEDS_REDIS = {"redis_two_processes"}


@pytest.mark.parametrize("path", EXAMPLES, ids=[path.stem for path in EXAMPLES])
def test_example(path: Path) -> None:
    if path.stem in NEEDS_REDIS and not os.environ.get("REDIS_URL"):
        pytest.skip("REDIS_URL is not set")
    result = subprocess.run([sys.executable, str(path)], capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stderr
