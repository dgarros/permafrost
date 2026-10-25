# Tasks

## 1. Container lifecycle and backend fixtures

- [x] 1.1 Add Testcontainers with Redis support to the development dependencies, select an explicit versioned Redis image, and regenerate `uv.lock`; verify `uv sync --locked` succeeds and base runtime dependencies are unchanged.
- [x] 1.2 Add `tests/integration/` with a lazy session-scoped Redis container fixture and function-scoped async backend fixtures using mapped endpoints, unique prefixes, scoped cleanup, and client closure; verify a marked backend round-trip test passes and the container is removed after pytest exits.
- [x] 1.3 Update the `redis` marker description, replace the `REDIS_URL`-gated smoke test in `tests/unit/test_redis.py`, and document Docker prerequisites and full, Redis-only, and Docker-free commands in `README.md`; verify `uv run pytest tests/unit` does not start a container and selected integration startup errors are not silently skipped.

## 2. Redis integration scenarios

- [x] 2.1 Add backend batch tests for binary payloads, missing entries in order, empty batches, root reads and writes, and prefix isolation; verify the targeted tests pass against containerized Redis.
- [x] 2.2 Add tests for node write expiry, TTL extension on fetch, and dimension roots without expiry using bounded TTL assertions and no long sleeps; verify the targeted tests pass against Redis.
- [x] 2.3 Add cold-reader nested-value reconstruction, dimension-copy independence, and explicit reload tests using separate clients and the existing `Process` helper; verify reader registries lack target values before reads and the tests pass against Redis.
- [x] 2.4 Add missing-child loader recovery and repopulation tests, cache-miss errors without a loader, and missing-dimension errors without a loader call; verify the repaired value can be read by a fresh isolated reader and all targeted tests pass.

## 3. Integration verification

- [x] 3.1 Run `uv run pytest tests/integration` and `uv run pytest` with Docker available; verify all selected integration tests execute successfully and existing tests retain their expected behavior.
- [x] 3.2 Run `uv run ty check`, `uv run ruff check`, and `uv run ruff format --check`; verify all checks pass without introducing `typing.Any`.

Verification on 2026-10-25 after rebasing onto `origin/main` at `a3fe39c`: `uv run ty check` and repository-wide `uv run ruff check` pass; `uv run ruff format --check` reports 99 files already formatted. The upstream changes resolve the lint and formatting issues observed before the rebase. The full suite still passes with 213 passed and 1 skipped.

Other verification: Redis selection: 12 passed; full suite: 213 passed, 1 skipped (the standalone Redis example needs `REDIS_URL`); Docker-free selection with an invalid `DOCKER_HOST`: 201 passed, 1 skipped, 12 deselected. Selecting a Redis test with that invalid endpoint raises a setup error rather than skipping. A temporary intentionally failing integration test confirmed the Redis container is removed after test failure; the temporary test was removed.

## 4. Directory-based test selection

- [x] 4.1 Move unit test modules to `tests/unit`, update imports and repository-root paths, and update CI and documentation to select `tests/unit` before `tests/integration`; verify the unit directory runs without Docker (201 passed, 1 skipped), integration directory passes (12 passed), and lint, formatting, and type checks pass.
