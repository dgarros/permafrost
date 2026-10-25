# dimension-sharing Specification

## Purpose

Lets several processes that use the same external cache read the dimensions that any of them wrote, and lets the calling application decide when a process picks up changes made by another process.

## Requirements

### Requirement: Write the root hash of a dimension to the external cache
When an external cache is configured, every change to a dimension SHALL write the dimension's new root hash to the external cache, after the new nodes of that change.

#### Scenario: Order of writes
- **WHEN** a user stores a value in a dimension with an external cache configured
- **THEN** the backend receives the new nodes before it receives the new root hash

### Requirement: Read a dimension that another process wrote
When a process reads a dimension that it does not hold in memory, the library SHALL read the root hash from the external cache and fetch the key map nodes and value nodes it needs by hash.

#### Scenario: Second process reads a key
- **WHEN** process A stores a value under `"k"` in `main`, and process B, which shares the external cache and has never read `main`, reads `"k"` from `main`
- **THEN** process B returns the value that process A stored

### Requirement: Dimension missing from memory and external cache
When a process reads a dimension that is neither in its memory nor in the external cache, the library SHALL raise a dimension-not-found error. The library SHALL NOT call the loader for this case.

#### Scenario: Unknown dimension
- **WHEN** a process reads a key from a dimension name that no process has written
- **THEN** the library raises a dimension-not-found error

#### Scenario: Key map node lost by the external cache
- **WHEN** a process reads a key from a dimension whose root hash is in the external cache but one key map node on the path to that key is not
- **THEN** the library raises a dimension-not-found error and does not call the loader

### Requirement: Reload a dimension on request
The library SHALL provide an operation that reads the current root hash of a dimension from the external cache and switches the dimension in memory to it. The library SHALL NOT check for a newer root hash on its own.

#### Scenario: Pick up another process's change
- **WHEN** process B holds `main` in memory, process A then changes `main`, and process B calls the reload operation for `main`
- **THEN** reads from `main` in process B return the values that process A wrote

#### Scenario: No reload
- **WHEN** process B holds `main` in memory, process A changes `main`, and process B does not call the reload operation
- **THEN** reads from `main` in process B return the values from before process A's change

### Requirement: Last write of a root hash wins
The library SHALL write the root hash of a dimension without checking whether another process changed it since. When two processes change the same dimension, the root hash written last SHALL replace the other.

#### Scenario: Two processes change the same dimension
- **WHEN** process A and process B both hold `main`, and each stores a different key, A first and then B
- **THEN** the root hash in the external cache is the one B wrote, and it does not hold the key that A stored

### Requirement: Dimension entries do not expire by idle time
The library SHALL write dimension root hash entries to the external cache with no expiry time.

#### Scenario: Root hash entry in Redis
- **WHEN** a user stores a value in a dimension with the Redis backend
- **THEN** the Redis entry for the dimension's root hash has no time to live
