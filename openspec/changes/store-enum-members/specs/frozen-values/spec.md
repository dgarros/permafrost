# Spec Delta

## MODIFIED Requirements

### Requirement: Supported value types
The library SHALL accept values made of any nesting of scalars (`str`, `int`, `float`, `bool`, `None`, `bytes`, `datetime.date`, `datetime.datetime`, and members of enum classes that subclass `str` or `int`), dictionaries, lists, tuples, sets, Pydantic dataclasses that inherit from the library base class, frozen Pydantic models, and types that have a registered type handler.

#### Scenario: Store a nested value
- **WHEN** a user stores a dictionary of lists of Pydantic dataclass instances whose fields hold tuples and strings
- **THEN** the library accepts the value and returns an equal read-only value

#### Scenario: Reject an unsupported type
- **WHEN** a user stores a value that contains an object of a type that is not supported and has no type handler
- **THEN** the library raises an error that names the type

#### Scenario: Store a member of a str enum without registration
- **WHEN** a user stores a value that contains a member of a class that subclasses `str` and `Enum`, without registering the class
- **THEN** the library accepts the value and returns the same enum member at the same place

#### Scenario: Reject a member of an enum that does not subclass str or int
- **WHEN** a user stores a member of an enum class that subclasses neither `str` nor `int` and has no type handler
- **THEN** the library raises an error that names the enum class

## ADDED Requirements

### Requirement: Enum members are stored as scalars
The library SHALL store a member of an enum class that subclasses `str` or `int` inside its parent node, as it stores other scalars, and not as a node of its own. This holds for a member used as a dictionary key or value, a list, tuple or set item, a model field, or the whole value. A type handler registered for the enum class SHALL take priority.

#### Scenario: Enum member as a model field
- **WHEN** a user freezes a frozen Pydantic model whose field `state` holds `State.PRESENT`, where `State` subclasses `str` and `Enum`
- **THEN** the returned model's `state` field is `State.PRESENT`, and the enum member is not one of the model's child nodes

#### Scenario: Enum member as a dictionary key
- **WHEN** a user freezes `{State.PRESENT: 1}`
- **THEN** the returned dictionary has the single key `State.PRESENT`, and that key is an instance of `State`

#### Scenario: Enum class with a registered type handler
- **WHEN** a user registers a type handler for an enum class that subclasses `str`, then stores one of its members
- **THEN** the library stores the member through the type handler, as a node of its own, with the same hash as before enum members were supported

#### Scenario: Integer enum member
- **WHEN** a user freezes `[Level.HIGH]`, where `Level` is an `IntEnum`
- **THEN** the returned list holds `Level.HIGH`, an instance of `Level`

### Requirement: Hash of an enum member
The hash of a value that contains an enum member SHALL depend on the enum class and on the member's value. An enum member and its plain value SHALL have different hashes, and members of two enum classes with the same value SHALL have different hashes. The hash of a value that contains no enum member SHALL be the same as before enum members were supported.

#### Scenario: Enum member and its plain value
- **WHEN** a user computes the hash of `State.PRESENT`, whose value is `"present"`, and the hash of `"present"`
- **THEN** the two hashes are different

#### Scenario: Same value in two enum classes
- **WHEN** a user computes the hash of `{"s": State.PRESENT}` and of `{"s": OtherState.PRESENT}`, where both members have the value `"present"`
- **THEN** the two hashes are different

#### Scenario: Same member in two values
- **WHEN** a user stores `{"s": State.PRESENT}` twice, under two keys
- **THEN** both values have the same hash and are the same node

### Requirement: Enum members are rebuilt from the external cache
When the library rebuilds a node from the external cache, it SHALL return the same enum member that was stored, not its plain value. By default the library SHALL find the enum class by its module and qualified name. A user SHALL be able to register an enum class under another name, for a class that cannot be imported by its module and qualified name.

#### Scenario: Read an enum member from the external cache
- **WHEN** a process stores `{"s": State.PRESENT}` with an external cache, and a second process that uses the same external cache reads the value
- **THEN** the second process returns a dictionary whose value for `"s"` is `State.PRESENT`, an instance of `State`

#### Scenario: Enum class registered under another name
- **WHEN** a user registers an enum class defined inside a function under a name of their choice, stores one of its members, and the value is rebuilt from its encoding
- **THEN** the rebuilt value holds the same enum member

#### Scenario: Enum class cannot be found when rebuilding
- **WHEN** the library rebuilds a value from the external cache whose enum class cannot be imported and is not registered, or whose stored value is no longer a member of the class
- **THEN** the library treats the value as a cache miss, as it does for a model class that cannot be found
