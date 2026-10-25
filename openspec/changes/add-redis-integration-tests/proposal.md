# Proposal

## Why

Redis behavior is mostly tested with fakeredis, and the one real-server test requires a manually configured `REDIS_URL`. Container-managed integration tests will exercise the actual Redis protocol and cache workflows reproducibly from pytest.

## What Changes

- Add Testcontainers with Redis support to the development dependencies and update the uv lockfile.
- Let pytest start and stop a Redis container, discover its mapped endpoint, and provide isolated asynchronous backend clients to integration tests.
- Replace the environment-gated Redis smoke test with a dedicated integration suite covering backend commands, TTLs, cold reads, dimension sharing and reload, and missing-node recovery.
- Retain fakeredis unit tests and a way to run them without Docker; document both test selections and Docker prerequisites.

## Capabilities

### New Capabilities

None. This change adds test infrastructure and coverage.

### Modified Capabilities

None. Existing requirements in `external-cache`, `dimension-sharing`, `value-loader`, and `cache-cleanup` define the behavior under test. Set `skip_specs: true` because library behavior and `SPEC.md` remain unchanged.

## Impact

Affected files include `pyproject.toml`, `uv.lock`, `tests/test_redis.py`, a new `tests/integration/` suite and fixtures, and test instructions in `README.md`. Running the Redis integration selection requires a reachable Docker daemon and permission to pull the selected Redis image. Redis and Testcontainers remain outside the base runtime dependencies. No public API changes or CI workflow additions are planned; this repository has no existing CI workflow.
