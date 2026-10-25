# frozen-values Specification

## Purpose

Converts the values that an application stores into read-only trees of nodes, identifies each node by a hash of its content, and holds each identical node only once in the process.

## Requirements

### Requirement: Supported value types
The library SHALL accept values made of any nesting of scalars (`str`, `int`, `float`, `bool`, `None`, `bytes`, `datetime.date`, `datetime.datetime`), dictionaries, lists, tuples, sets, Pydantic dataclasses that inherit from the library base class, frozen Pydantic models, and types that have a registered type handler.

#### Scenario: Store a nested value
- **WHEN** a user stores a dictionary of lists of Pydantic dataclass instances whose fields hold tuples and strings
- **THEN** the library accepts the value and returns an equal read-only value

#### Scenario: Reject an unsupported type
- **WHEN** a user stores a value that contains an object of a type that is not supported and has no type handler
- **THEN** the library raises an error that names the type

### Requirement: Type handlers for other types
The library SHALL let a user register a type handler for a Python type. The handler tells the library how to convert an instance into a supported form, hash it and rebuild it. After registration, values of that type are stored like supported values.

#### Scenario: Store an object with a registered handler
- **WHEN** a user registers a type handler for a custom class and stores an instance of that class
- **THEN** reading the value returns an equal instance of the custom class

### Requirement: Returned values are read-only
Every value that the library returns SHALL be read-only at every level. Assigning an attribute, setting or deleting a key, or adding, removing or replacing an item SHALL raise an error.

#### Scenario: Set a key on a returned dictionary
- **WHEN** a user sets a key on a dictionary returned by the library
- **THEN** the library raises an error and the stored value is unchanged

#### Scenario: Append to a returned list
- **WHEN** a user appends an item to a list returned by the library
- **THEN** the library raises an error and the stored value is unchanged

#### Scenario: Assign a field on a returned model
- **WHEN** a user assigns a field on a Pydantic dataclass instance returned by the library
- **THEN** an error is raised and the stored value is unchanged

### Requirement: Read-only collections behave like built-in collections for reading
Read-only dictionaries, lists, tuples and sets returned by the library SHALL support the same read operations as the matching built-in types, including indexing, iteration, length, membership and comparison for equality with built-in values that have the same content.

#### Scenario: Compare a returned list with a built-in list
- **WHEN** a user stores `[1, 2, 3]` and compares the returned value with `[1, 2, 3]`
- **THEN** the comparison is true

### Requirement: Stored data is independent of the input object
When a user passes a mutable object, the library SHALL store a read-only copy. Later changes to the original object SHALL NOT change the stored value.

#### Scenario: Change the input after storing it
- **WHEN** a user stores a dictionary and then adds a key to the original dictionary
- **THEN** reading the stored value returns the dictionary without the added key

### Requirement: Models are returned as the user's own class
For Pydantic dataclasses and Pydantic models, the library SHALL return instances of the user's own class with the same field values.

#### Scenario: Read back a Pydantic dataclass
- **WHEN** a user stores an instance of their Pydantic dataclass `Device`
- **THEN** the returned value is an instance of `Device` and is equal to the stored instance

### Requirement: Validation happens only at the edge
The library SHALL NOT run Pydantic validation or `__post_init__` when it creates, copies or updates model instances internally. Validating data before it is passed to the library is the responsibility of the calling application and is optional.

#### Scenario: Update a field without validation
- **WHEN** a user stores an instance of a Pydantic dataclass whose `__post_init__` counts its calls, then updates one field through the library
- **THEN** the call count does not increase

### Requirement: Content hash
The library SHALL give each node a hash computed from its content and the content of all nodes it contains. Nodes with the same content SHALL have the same hash, in any process and whatever the insertion order of dictionary keys or set items.

#### Scenario: Same content in a different order
- **WHEN** a user stores `{"a": 1, "b": 2}` and `{"b": 2, "a": 1}`
- **THEN** both values have the same hash

#### Scenario: Different content
- **WHEN** a user stores `{"a": 1}` and `{"a": 2}`
- **THEN** the two values have different hashes

#### Scenario: Same items in different collection types
- **WHEN** a user stores the list `[1, 2]` and the tuple `(1, 2)`
- **THEN** the two values have different hashes

### Requirement: Each identical node is held once
The library SHALL hold at most one node object in the process for each hash. When two values, two keys or two parts of one value contain nodes with the same content, they SHALL refer to the same node object.

#### Scenario: Same sub-value in two keys
- **WHEN** a user stores two values that both contain an equal nested dictionary
- **THEN** the nested dictionary in both returned values is the same object

### Requirement: Nodes that nothing refers to are freed
The registry of nodes SHALL NOT keep a node in memory on its own. When no dimension and no cached value refers to a node, the process SHALL free it.

#### Scenario: Value is no longer referred to
- **WHEN** a value is evicted, no other value or dimension contains its nodes, and the user holds no reference to it
- **THEN** the registry no longer holds its nodes
