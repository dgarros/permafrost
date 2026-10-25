"""Run each script of the examples directory."""

import os
import subprocess
import sys
from pathlib import Path

import pytest

NEEDS_REDIS = {"redis_two_processes"}
EXAMPLES = [
    pytest.param(
        path,
        id=path.stem,
        marks=pytest.mark.skipif(
            path.stem in NEEDS_REDIS and not os.environ.get("REDIS_URL"), reason="REDIS_URL is not set"
        ),
    )
    for path in sorted((Path(__file__).parent.parent / "examples").glob("*.py"))
]


@pytest.mark.parametrize("path", EXAMPLES)
def test_example(path: Path) -> None:
    result = subprocess.run([sys.executable, str(path)], capture_output=True, text=True, timeout=60, check=False)
    assert result.returncode == 0, result.stderr
