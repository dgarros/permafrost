# Spec Delta

## MODIFIED Requirements

### Requirement: Pluggable backend interface
The library SHALL define a backend interface of `async` operations: get several nodes by hash, set several nodes, extend the expiry time of several hashes, and get, set and delete the root hash of a dimension. Any object that implements this interface SHALL be usable as the external cache.

#### Scenario: Use a backend written by the application
- **WHEN** a user configures the library with an in-process backend that implements the interface
- **THEN** the library stores and fetches nodes through that backend

#### Scenario: Delete a root hash that the backend does not hold
- **WHEN** the library asks a backend to delete the root hash of a dimension that it does not hold
- **THEN** the backend returns without error

#### Scenario: Delete a root hash in Redis
- **WHEN** a user deletes a dimension with the Redis backend
- **THEN** Redis no longer holds the entry for the dimension's root hash, and still holds the node entries
