"""Run the type checker on the library, the tests and the examples, so that a type error fails the tests."""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parents[2]


def test_type_check() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "ty", "check", "--output-format", "concise"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
