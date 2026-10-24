# Permafrost

Permafrost is a Python library that stores deeply nested, read-only data across many dimensions, such as branches, and stores each identical piece of data only once.

`SPEC.md` is the reference for what the library does and how it is built. Read it before changing code. When a change contradicts the spec, update the spec in the same change or ask first.

## Project setup

- Python 3.12 or later, managed with `uv`.
- Source code is in `src/permafrost/`.
- Run the tests with `uv run pytest`.
