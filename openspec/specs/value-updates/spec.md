# value-updates Specification

## Purpose

Lets a user change stored data only through operations that return a new version of a value, leave the previous version unchanged, and share every unchanged node with it.

## Requirements

### Requirement: Paths inside a value
Update operations SHALL take a path made of a sequence of steps. A step is a dictionary key, a list or tuple index, or a model field name. A path that does not exist in the value SHALL raise an error, except where a requirement below allows it.

#### Scenario: Path through a dictionary, a list and a model
- **WHEN** a user sets the path `("devices", 0, "name")` on a dictionary whose `"devices"` key holds a list of models
- **THEN** the new version has the new name on the first model of the list

#### Scenario: Path to a missing list index
- **WHEN** a user sets the path `("devices", 5)` on a list of two items
- **THEN** the library raises an error

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

### Requirement: Delete a value at a path
The library SHALL provide an operation that deletes a dictionary key or a list item at a path and returns a new version. Deleting a model field SHALL raise an error.

#### Scenario: Delete a dictionary key
- **WHEN** a user deletes `("a", "b")` from `{"a": {"b": 1, "c": 2}}`
- **THEN** the operation returns `{"a": {"c": 2}}`

#### Scenario: Delete a list item
- **WHEN** a user deletes `(1,)` from `[10, 20, 30]`
- **THEN** the operation returns `[10, 30]`

### Requirement: Merge a partial value
The library SHALL provide an operation that merges a partial value into an existing value and returns a new version. Dictionaries SHALL merge key by key and models field by field, at every level. A key or field that exists only in the partial value SHALL be added for dictionaries. Any other value in the partial value SHALL replace the existing one.

#### Scenario: Merge nested dictionaries
- **WHEN** a user merges `{"a": {"c": 3}}` into `{"a": {"b": 1}, "d": 4}`
- **THEN** the operation returns `{"a": {"b": 1, "c": 3}, "d": 4}`

#### Scenario: Merge into a model
- **WHEN** a user merges `{"name": "r2"}` into a model with fields `name="r1"` and `site="paris"`
- **THEN** the operation returns a model of the same class with `name="r2"` and `site="paris"`

#### Scenario: Merge a scalar over a dictionary
- **WHEN** a user merges `{"a": 5}` into `{"a": {"b": 1}}`
- **THEN** the operation returns `{"a": 5}`

### Requirement: List behavior during a merge
When a merge meets a list on both sides, the user SHALL select "replace" or "append". "Replace" uses the list from the partial value. "Append" returns the items of the existing list followed by the items of the partial list. The default SHALL be "replace".

#### Scenario: Merge lists with replace
- **WHEN** a user merges `{"tags": ["b"]}` into `{"tags": ["a"]}` with "replace"
- **THEN** the operation returns `{"tags": ["b"]}`

#### Scenario: Merge lists with append
- **WHEN** a user merges `{"tags": ["b"]}` into `{"tags": ["a"]}` with "append"
- **THEN** the operation returns `{"tags": ["a", "b"]}`

### Requirement: Updates share unchanged nodes
An update SHALL create new nodes only for the changed node and its parents up to the root of the value. Every other node of the new version SHALL be the same object as in the previous version.

#### Scenario: Change one leaf of a large value
- **WHEN** a user sets one field deep inside a value that has two sibling subtrees
- **THEN** the unchanged sibling subtree in the new version is the same object as in the previous version

### Requirement: Updates that change nothing return the same value
When an update produces content equal to the existing value, the library SHALL return a value with the same hash as the existing value.

#### Scenario: Set a value to its current content
- **WHEN** a user sets `("a",)` to `1` on `{"a": 1}`
- **THEN** the returned value has the same hash as the existing value
