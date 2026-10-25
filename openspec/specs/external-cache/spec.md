# external-cache Specification

## Purpose

Lets a process fetch nodes that are not in its memory from an optional cache service outside the process, starting with Redis, with a number of requests that grows with the depth of a value rather than its number of nodes.

## Requirements

### Requirement: The external cache is optional
The library SHALL work without an external cache. Without one, every node SHALL stay in the in-memory cache until it is evicted or freed.

#### Scenario: Use without an external cache
- **WHEN** a user stores and reads values with no external cache configured
- **THEN** all operations succeed and no network request is made

### Requirement: Pluggable backend interface
The library SHALL define a backend interface of `async` operations: get several nodes by hash, set several nodes, extend the expiry time of several hashes, and get and set the root hash of a dimension. Any object that implements this interface SHALL be usable as the external cache.

#### Scenario: Use a backend written by the application
- **WHEN** a user configures the library with an in-process backend that implements the interface
- **THEN** the library stores and fetches nodes through that backend

### Requirement: Redis backend
The library SHALL provide a backend for Redis that uses the `asyncio` client of the `redis` package. The `redis` package SHALL be an optional dependency.

#### Scenario: Import without the redis package
- **WHEN** the `redis` package is not installed and a user imports the library without using the Redis backend
- **THEN** the import succeeds

### Requirement: Each node is one entry
The external cache SHALL hold each node as one entry under its hash, holding the serialized content of the node with each child written as its hash. A node shared by several values or dimensions SHALL be written once.

#### Scenario: Shared node written once
- **WHEN** a user stores two values that share a nested dictionary
- **THEN** the external cache holds one entry for that nested dictionary

### Requirement: Write new nodes in one request
When the library writes a value or key map change, it SHALL send all the nodes that this change created in one request to the backend.
#### Scenario: Store a value with many nodes
- **WHEN** a user stores a value of 50 new nodes
- **THEN** the library calls the backend's set operation once for these nodes

### Requirement: Fetch a value one level at a time
When a value is not in memory, the library SHALL fetch its root from the external cache, then fetch all missing nodes of the next level in one request, and repeat until the value is complete. It SHALL then rebuild the value in memory with direct references between nodes.

#### Scenario: Fetch a value of depth 3
- **WHEN** a process reads a value of depth 3 that is in the external cache and not in memory
- **THEN** the library makes at most 3 get requests to the backend and returns a value equal to the stored one

#### Scenario: Nodes already in memory are not fetched
- **WHEN** some nodes of the value are already in the in-memory cache
- **THEN** the library does not request these nodes from the backend

### Requirement: Fetched nodes are not checked for staleness
The library SHALL treat a node fetched by hash as correct for that hash and SHALL NOT check it again later.

#### Scenario: Read a fetched node again
- **WHEN** a process reads a value it fetched earlier and that is still in memory
- **THEN** the library makes no request to the backend

### Requirement: Expiry of node entries
The library SHALL set a configurable expiry time on each node entry it writes, 24 hours by default, and SHALL extend the expiry time of the nodes it fetches or reads from the external cache. The library SHALL NOT delete node entries from the external cache.

#### Scenario: Expiry set on write
- **WHEN** a user stores a value with the Redis backend and an expiry time of 24 hours
- **THEN** each new node entry in Redis has a time to live of about 24 hours

#### Scenario: Expiry extended on read
- **WHEN** a process fetches a value from the external cache
- **THEN** the library extends the expiry time of the fetched node entries

### Requirement: Values not fully in the external cache
When the external cache holds only some of the nodes of a value, the library SHALL treat the value as a cache miss.

#### Scenario: One child entry is missing
- **WHEN** the external cache holds the root of a value but has lost one of its children
- **THEN** the library treats the read as a cache miss as described in the value-loader capability
