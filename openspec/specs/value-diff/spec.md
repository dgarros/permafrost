# value-diff Specification

## Purpose

Lets a user find out whether two stored values are equal and which paths differ between them, with a cost that grows with the size of the change rather than the size of the values.

## Requirements

### Requirement: Equality by hash
Comparing two stored values for equality SHALL compare their hashes and SHALL NOT read their children. This comparison SHALL be a regular, not `async`, function.

#### Scenario: Two equal values built separately
- **WHEN** a user stores two separately built values with the same content and compares them
- **THEN** the comparison is true

### Requirement: Diff between two values
The library SHALL return the diff between two values as a list of entries. Each entry SHALL give the path, the kind of change (added, removed or changed), the old content and the new content.

#### Scenario: Changed nested key
- **WHEN** a user requests the diff between `{"a": {"b": 1}}` and `{"a": {"b": 2}}`
- **THEN** the diff holds one "changed" entry for the path `("a", "b")` with old content `1` and new content `2`

#### Scenario: Added and removed keys
- **WHEN** a user requests the diff between `{"a": 1}` and `{"b": 2}`
- **THEN** the diff holds a "removed" entry for `("a",)` and an "added" entry for `("b",)`

#### Scenario: Equal values
- **WHEN** a user requests the diff between two values with the same hash
- **THEN** the diff is empty

### Requirement: Diff of lists, sets and models
Lists and tuples SHALL be compared index by index, with items past the end of the shorter side reported as added or removed. Sets SHALL report each item present on only one side as added or removed. Models of the same class SHALL be compared field by field. Values of different types or model classes SHALL be reported as one "changed" entry.

#### Scenario: List with an extra item
- **WHEN** a user requests the diff between `[1, 2]` and `[1, 2, 3]`
- **THEN** the diff holds one "added" entry for the path `(2,)` with new content `3`

#### Scenario: Different types at the same path
- **WHEN** a user requests the diff between `{"a": [1]}` and `{"a": {"x": 1}}`
- **THEN** the diff holds one "changed" entry for the path `("a",)`

### Requirement: Diff skips identical subtrees
Computing a diff SHALL NOT read the children of any pair of nodes that have the same hash.

#### Scenario: One change in a large value
- **WHEN** a user requests the diff between two versions of a value with 1,000 subtrees that differ in one subtree
- **THEN** the library reads only the nodes on the path to the changed subtree and the children of the nodes on that path

### Requirement: Diff of one key in two dimensions
The library SHALL return the diff between the values of the same key in two dimensions. A key that exists in only one dimension SHALL produce one "added" or "removed" entry for the whole value.

#### Scenario: Key changed on a branch
- **WHEN** a user changes one field of the value under a key in dimension `branch-a` and requests the diff of that key between `main` and `branch-a`
- **THEN** the diff holds one "changed" entry for that field
