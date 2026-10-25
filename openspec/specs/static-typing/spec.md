# static-typing Specification

## Purpose

Gives a type checker exact types for the public API, so that code that stores and reads values through Permafrost is checked without run-time tests, and so that the library itself passes a type check.

## Requirements

### Requirement: No `Any` in the public API
Every public function, method, attribute and type alias of the library SHALL declare its parameter and return types without `Any`. Where the type of a position cannot be known statically, the declared type SHALL be `object`, so that a type checker requires the caller to narrow it.

#### Scenario: Lint rejects `Any`
- **WHEN** a function in the library declares a parameter or a return type as `Any`
- **THEN** the lint check of the project fails on that line

#### Scenario: Diff content is `object`
- **WHEN** a user reads the old or new content of a diff entry
- **THEN** the type checker reports `object`, and reading an attribute of it without narrowing is a type error

### Requirement: Models keep their class in types
When a user freezes, updates, merges or stores a model, the type checker SHALL report the model's own class as the result. This holds for Pydantic dataclasses that inherit from the Permafrost base class and for Pydantic models.

#### Scenario: Freeze a model
- **WHEN** a user calls `freeze()` on a `Device` instance
- **THEN** the type checker reports `Device` as the type of the result

#### Scenario: Update a model at a path
- **WHEN** a user calls `set_in()`, `delete_in()` or `merge()` with a `Device` as the value
- **THEN** the type checker reports `Device` as the type of the result

### Requirement: Scalars keep their type
When a user freezes a scalar, the type checker SHALL report the scalar's own type.

#### Scenario: Freeze an integer
- **WHEN** a user calls `freeze()` on an `int`
- **THEN** the type checker reports `int`

### Requirement: Read-only collections are generic
The read-only dictionary, list, tuple and set classes SHALL take type parameters for their keys and items. Freezing a `Mapping[K, V]` SHALL be typed as the read-only dictionary of `K` to `V`; a `Sequence[T]` as the read-only list of `T`; a tuple of `T` as the read-only tuple of `T`; a set of `T` as the read-only set of `T`. A read-only tuple has one item type: a tuple of mixed types is typed with the union of its item types.

#### Scenario: Freeze a dictionary of scalars
- **WHEN** a user calls `freeze()` on a value typed `dict[str, int]`
- **THEN** the type checker reports `FrozenDict[str, int]`, and reading a key gives `int`

#### Scenario: Nested value declared with an abstract type
- **WHEN** a user calls `freeze()` on a value typed `dict[str, Sequence[int]]`
- **THEN** the type checker reports `FrozenDict[str, Sequence[int]]`, and the read-only list that the value holds at run time is a `Sequence[int]`

#### Scenario: Nested value declared with a mutable type
- **WHEN** a user calls `freeze()` on a value typed `dict[str, list[int]]`
- **THEN** the type checker reports `FrozenDict[str, list[int]]`, and the value holds a read-only list at run time, as the documentation states

#### Scenario: Reading a read-only collection
- **WHEN** a user iterates over a `FrozenDict[str, Device]` or indexes a `FrozenList[Device]`
- **THEN** the type checker reports `str` for the keys and `Device` for the values and items

### Requirement: The store is typed by its value type
A store SHALL take a type parameter for the type of its values. Reading a key SHALL be typed as that type, storing SHALL accept that type, updating SHALL take a function from that type to that type or to an awaitable of it, and the loader SHALL be typed as returning an awaitable of that type.

#### Scenario: Store of models
- **WHEN** a user creates a `Store[Device]` and reads a key
- **THEN** the type checker reports `Device` as the type of the value

#### Scenario: Loader of another type
- **WHEN** a user creates a `Store[Device]` with a loader that returns a `str`
- **THEN** the type checker reports an error on the loader argument

#### Scenario: Store of dictionaries
- **WHEN** a user creates a `Store[Mapping[str, int]]`, stores a `dict[str, int]` and reads it back
- **THEN** the type checker accepts the stored value and reports `Mapping[str, int]` for the value read

### Requirement: Type handlers are typed by their class
Registering a type handler SHALL check the `encode` function against the registered class and SHALL type the result of `decode` as that class.

#### Scenario: Encode function for another class
- **WHEN** a user registers a handler for `Prefix` with an `encode` function whose parameter is typed `Device`
- **THEN** the type checker reports an error on the `encode` argument

### Requirement: Path steps are typed
A path SHALL be typed as a sequence of steps, where a step is a scalar or a tuple of scalars. The path of a diff entry SHALL be typed as a tuple of steps.

#### Scenario: Path with a list as a step
- **WHEN** a user passes a path that contains a list as a step
- **THEN** the type checker reports an error on the path argument

### Requirement: The library passes the type check
The type check SHALL report no error on the library, the tests and the examples, and SHALL run as part of the test suite so that a type error fails the tests. A test or example that passes a wrong type on purpose SHALL mark the line with an ignore comment that names the rule it ignores.

#### Scenario: Test suite runs the type check
- **WHEN** a user runs the tests
- **THEN** the type check runs and the tests fail if it reports an error

#### Scenario: Deliberate wrong type in a test
- **WHEN** a test passes a value of a wrong type to check that the library rejects it
- **THEN** the line carries an ignore comment that names the rule, and the type check reports no error

### Requirement: Documentation of the rule for exact types
The documentation SHALL state when the declared types are exact: values declared with models, scalars, or the abstract read-only types `Mapping`, `Sequence` and `AbstractSet`. It SHALL state that a value declared as `list`, `dict` or `set` inside another value holds the read-only class at run time, and SHALL show how to declare a typed store.

#### Scenario: Reader finds the rule
- **WHEN** a user reads the README section on type checking
- **THEN** the section states the rule, the exception for mutable declarations, and shows a `Store[Device]` example that runs as written
