"""Run each Python example of README.md as written."""

import re
from pathlib import Path

import pytest

README = Path(__file__).parent.parent / "README.md"
BLOCKS = re.findall(r"```python\n(.*?)```", README.read_text(), re.DOTALL)


@pytest.mark.parametrize("code", BLOCKS, ids=[f"example-{i}" for i in range(len(BLOCKS))])
def test_readme_example(code: str) -> None:
    exec(compile(code, str(README), "exec"), {"__name__": "readme_example"})
