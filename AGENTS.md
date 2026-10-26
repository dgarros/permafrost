# Permafrost

Permafrost is a Python library that stores deeply nested, read-only data across many dimensions, such as branches, and stores each identical piece of data only once.

`SPEC.md` is the reference for what the library does and how it is built. Read it before changing code. When a change contradicts the spec, update the spec in the same change or ask first.

## Project setup

- Python 3.12 or later, managed with `uv`.
- Source code is in `src/permafrost/`.
- Run the tests with `uv run pytest`. They include the type check, which you can also run alone with `uv run ty check`.
- Lint and format with `uv run ruff check` and `uv run ruff format`. Do not use `typing.Any`: declare an exact type, or `object` where the type is open.
- Give every function, method and class in `src/permafrost/` a docstring, including internal ones whose names start with `_`. `ruff check` reports a missing docstring on public names only, so check internal ones yourself.
