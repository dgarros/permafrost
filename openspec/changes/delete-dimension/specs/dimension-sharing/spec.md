# Spec Delta

## ADDED Requirements

### Requirement: Delete the root hash of a dimension from the external cache
When an external cache is configured, deleting a dimension SHALL remove its root hash entry from the external cache before the library removes the dimension from memory. The library SHALL delete a dimension whose root hash is in the external cache even when the dimension is not in memory. The library SHALL NOT delete node entries from the external cache: they expire on their own. Another process that holds the dimension in memory SHALL keep it until that process deletes it.

#### Scenario: Second process reads a deleted dimension
- **WHEN** process A deletes `branch-a`, and process B, which shares the external cache and does not hold `branch-a` in memory, reads a key from `branch-a`
- **THEN** process B raises a dimension-not-found error

#### Scenario: Create a dimension that another process deleted
- **WHEN** process A deletes `branch-a`, and process B, which shares the external cache and does not hold `branch-a` in memory, creates `branch-a`
- **THEN** process B creates the dimension and does not raise a dimension-exists error

#### Scenario: Delete a dimension that is only in the external cache
- **WHEN** process A created `branch-a`, and process B, which shares the external cache and has never read `branch-a`, deletes `branch-a`
- **THEN** the external cache no longer holds the root hash of `branch-a`

#### Scenario: Node entries stay in the external cache
- **WHEN** a user deletes a dimension with an external cache configured
- **THEN** the library sends no request that deletes node entries, and the next cleanup does not extend the expiry time of the key map nodes that only the deleted dimension referred to

#### Scenario: Another process holds the deleted dimension in memory
- **WHEN** process B holds `branch-a` in memory, process A deletes `branch-a`, and process B then deletes `branch-a`
- **THEN** the deletion in process B removes `branch-a` from its memory and does not raise an error

#### Scenario: Failed deletion in the external cache
- **WHEN** a user deletes a dimension and the backend raises an error while removing the root hash
- **THEN** the library raises that error and the dimension stays in memory
