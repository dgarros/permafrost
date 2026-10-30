# Spec Delta

## MODIFIED Requirements

### Requirement: Any name can be a dimension
Dimension names SHALL be strings with no meaning for the library. A dimension SHALL exist from the time a user creates it until a user deletes it, and creating a dimension with a name that already exists SHALL raise an error.

#### Scenario: Create an empty dimension
- **WHEN** a user creates the dimension `snapshot-2026-10-24` with no source
- **THEN** the dimension exists and has no keys

#### Scenario: Create a dimension again after deleting it
- **WHEN** a user deletes the dimension `branch-a` and then creates a dimension named `branch-a` with no source
- **THEN** the library creates it, and it has no keys

## ADDED Requirements

### Requirement: Delete a dimension
The library SHALL let a user delete a dimension by name. After the deletion, reading the dimension SHALL raise a dimension-not-found error. Deleting a dimension SHALL NOT change any other dimension, including dimensions created from it or from which it was created. The library SHALL hold no reference to the key map of the deleted dimension, so that Python frees the key map nodes that no other dimension refers to. Deleting a dimension that is neither in memory nor in the external cache SHALL raise a dimension-not-found error.

#### Scenario: Read a deleted dimension
- **WHEN** a user deletes the dimension `branch-a` and then reads the key `"device-1"` from `branch-a`
- **THEN** the library raises a dimension-not-found error and does not call the loader

#### Scenario: Other dimensions keep their data
- **WHEN** `branch-a` was created from `main`, a user changes `"device-1"` in `branch-a`, and then deletes `branch-a`
- **THEN** reading `"device-1"` from `main` returns the value from before the change, and `main` has the same root hash as before the deletion

#### Scenario: Key map nodes are freed
- **WHEN** a user changes `"device-1"` in `branch-a`, created from `main`, and then deletes `branch-a`
- **THEN** the registry no longer holds the key map nodes that only `branch-a` referred to, and still holds every key map node of `main`

#### Scenario: Delete a dimension that does not exist
- **WHEN** a user deletes a dimension name that is neither in memory nor in the external cache
- **THEN** the library raises a dimension-not-found error

#### Scenario: Delete a dimension twice
- **WHEN** a user deletes the dimension `branch-a` and then deletes `branch-a` again
- **THEN** the second deletion raises a dimension-not-found error
