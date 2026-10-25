# Design

## Context

See `proposal.md` for motivation. `tests/test_redis.py` currently mixes fakeredis unit tests with one `REDIS_URL` smoke test. `tests/process.py` provides isolated registries for simulating independent processes, preventing reads from accidentally succeeding through globally shared in-memory nodes. Pytest uses automatic asyncio mode and runs ty across the tests as well as the library.

## Goals / Non-Goals

**Goals:** Exercise Redis through its real asynchronous client, manage the server lifecycle from pytest, isolate tests, and prove reads cross the external-cache boundary.

**Non-Goals:** Change library behavior, replace fakeredis unit tests, add a Redis version matrix, add CI infrastructure, or change the standalone example's `REDIS_URL` interface.

## Decisions

### Separate integration tests with the existing Redis marker

Add `tests/integration/test_redis.py` and fixtures scoped to that directory. Mark the module `redis`, updating the existing marker description. `uv run pytest` includes integration tests and requires Docker; `uv run pytest -m 'not redis'` runs the existing suite without creating a container. `uv run pytest -m redis` explicitly runs the integration suite. An unavailable Docker daemon or failed startup fails the selected integration tests with an actionable error; do not silently skip them or convert arbitrary startup exceptions into skips.

Keep fakeredis tests in `tests/test_redis.py`; remove its environment-gated smoke test after replacing its coverage. Retaining the environment gate would leave real Redis coverage dependent on external setup.

### Session container, function-scoped clients

Use Testcontainers' Redis support as a development dependency, updating `uv.lock`. A lazy synchronous session fixture manages one Redis container with a context manager and the explicit image tag `redis:7.4.2-alpine`. Use Testcontainers' mapped host and port rather than assuming localhost or port 6379. Startup must establish Redis readiness before yielding an endpoint.

Function-scoped asynchronous fixtures create `RedisBackend.from_url` clients using a unique prefix for each test. Keep clients on the function's event loop and close them in `finally`. Tests involving separate stores use separate clients with the same prefix. Remove only that test's prefixed entries on teardown, using scan-based cleanup; never flush a shared database. Container teardown runs even when a test fails. A container per test would repeat image startup unnecessarily, while a session-scoped async client risks crossing event loops.

### Reuse existing contracts and process isolation

Add focused scenarios for:

- Backend batch writes and ordered reads containing misses, binary payloads, empty batches, root get/set, and namespace isolation.
- Expiry on node writes, refresh after a fetch, and dimension root entries with no expiry. Set a shorter TTL explicitly before a refresh and compare bounded TTLs without long sleeps.
- Nested values reconstructed through a cold reader using `Process` and a separate client; verify keys, content, and root hashes.
- Independent reader state remaining unchanged until `reload()`, and dimension copies preserving independent values after an update.
- Missing child nodes causing loader fallback and repopulating Redis, with a subsequent cold read succeeding. Verify missing values without a loader raise `CacheMissError`, and missing dimension roots raise `DimensionNotFoundError` without invoking a loader.

Use the existing `Process` helper for independent registries and assert the target value is absent from the reader's registry before cold reads. Separate clients alone do not provide this isolation. Delete known Redis node entries to simulate cache loss deterministically; expiry semantics are checked with TTL commands rather than timing races. The library itself continues never to delete cached nodes.

### Document the development workflow

Add README instructions for dependency installation, Docker availability and image pulls, full-suite execution, and marker-based selections. Keep Testcontainers out of the base runtime dependencies and preserve import-without-redis coverage. The standalone Redis example retains its manually supplied endpoint and existing example-test gate.

## Risks / Trade-offs

- Docker or image-pull failures → report them when integration tests are selected and document prerequisites; retain the Docker-free selection.
- Async clients reused across loops → create and close every client within its function-scoped asynchronous fixture.
- Cached nodes masking Redis reads → use isolated registries and explicit cold-state assertions.
- Session container state leaking between tests → unique prefixes, scoped cleanup, and an isolation scenario.
- TTL timing variability → use generous bounded assertions and explicit TTL reductions without wall-clock waits.
- A dependency's broad type annotations leaking into tests → declare exact fixture and helper types or `object`, and verify with ty; do not introduce `typing.Any`.

## Migration Plan

Add dependencies and fixtures, replace the existing smoke test with the new scenarios, document commands, then run the Redis selection, Docker-free selection, full suite, type checker, and Ruff. Record actual test results and any environment blocker in the implementation report. Rollback removes only test infrastructure, dependency changes, and documentation.
