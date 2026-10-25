# Spec Delta

## MODIFIED Requirements

### Requirement: Set a value at a path
The library SHALL provide an operation that sets or replaces the value at a path and returns a new version. Setting a missing key in a dictionary SHALL add the key. An empty path SHALL raise an error, because the result would be the new value and not a new version of the existing one.

#### Scenario: Replace a nested value
- **WHEN** a user sets `("a", "b")` to `2` on `{"a": {"b": 1}}`
- **THEN** the operation returns `{"a": {"b": 2}}` and the previous version still reads `{"a": {"b": 1}}`

#### Scenario: Add a dictionary key
- **WHEN** a user sets `("a", "c")` to `3` on `{"a": {"b": 1}}`
- **THEN** the operation returns `{"a": {"b": 1, "c": 3}}`

#### Scenario: Set a field that the model does not have
- **WHEN** a user sets a field name that the model class does not define
- **THEN** the library raises an error

#### Scenario: Set with an empty path
- **WHEN** a user sets the path `()` to `[1]` on `{"a": 1}`
- **THEN** the library raises an error and the value is unchanged
