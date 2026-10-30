# Spec Delta

## MODIFIED Requirements

### Requirement: Values that no dimension refers to
A value that no dimension refers to any more SHALL stay in the in-memory cache until eviction removes it. When a user deletes a dimension and asks for its values to be evicted, the library SHALL evict at once the values of the deleted dimension that no other dimension in memory refers to.

#### Scenario: Key deleted
- **WHEN** a user deletes the only key that referred to a value
- **THEN** the value stays in the in-memory cache until cleanup evicts it by idle time or memory limit

#### Scenario: Dimension deleted without evicting its values
- **WHEN** a user deletes a dimension without asking for its values to be evicted, and no external cache is configured
- **THEN** the values of the deleted dimension stay in the in-memory cache, and the number of cached values does not change

#### Scenario: Dimension deleted and its values evicted
- **WHEN** `branch-a` was created from `main` with 100 keys, a user stores a new value under `"device-1"` in `branch-a`, and then deletes `branch-a` and asks for its values to be evicted
- **THEN** the in-memory cache no longer holds the new value of `"device-1"`, and still holds the 100 values that `main` refers to

#### Scenario: Value under two keys of the deleted dimension
- **WHEN** the deleted dimension holds the same value under two keys, `main` holds that value under one of these keys, and a user deletes the dimension and asks for its values to be evicted
- **THEN** the in-memory cache still holds the value

#### Scenario: Value that another dimension holds under another key
- **WHEN** the deleted dimension holds a value under `"a"`, `main` holds the same value under `"b"` and not under `"a"`, and a user deletes the dimension and asks for its values to be evicted
- **THEN** the in-memory cache still holds the value

#### Scenario: Read after the values of a deleted dimension were evicted
- **WHEN** a user deletes `branch-a` and asks for its values to be evicted, and another dimension that is not in memory but is in the external cache refers to one of these values
- **THEN** a read of that value from the other dimension fetches it from the external cache, or calls the loader
