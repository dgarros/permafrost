# value-loader Specification

## Purpose

Lets the calling application reload a value from its own durable storage when neither the in-memory cache nor the external cache holds it, because the library only caches data and never persists it.

## Requirements

### Requirement: Register a loader
The library SHALL let the calling application register one `async` loader function. The library SHALL call it with one dimension name and one key, and the loader SHALL return the value for that key.

#### Scenario: Loader is called on a cache miss
- **WHEN** a key exists in the key map of `main`, its value is in neither cache, and a loader is registered
- **THEN** the library awaits the loader once with `"main"` and the key, and returns the value that the loader returned

### Requirement: Loaded values are stored like any other value
The library SHALL store the value that the loader returns in the same way as a value that a user stores, including writing its nodes to the external cache, and SHALL then return it.

#### Scenario: Second read after a load
- **WHEN** the loader returned a value and the user reads the same key again
- **THEN** the library returns the value from memory and does not call the loader again

### Requirement: Loaded value with a different hash
When the loader returns a value whose hash differs from the hash in the key map, the library SHALL store the loaded value under the key in that dimension, so the dimension's root hash changes.

#### Scenario: Application storage holds newer data
- **WHEN** the loader returns content different from the content that the key map refers to
- **THEN** the library returns the loaded content and the key map of the dimension refers to its hash

### Requirement: Cache miss without a loader
When a value is a cache miss and no loader is registered, the library SHALL raise a cache-miss error that names the dimension and the key.

#### Scenario: No loader registered
- **WHEN** the value under a key is in neither cache and no loader is registered
- **THEN** the library raises a cache-miss error with the dimension and the key

### Requirement: Loader errors reach the caller
When the loader raises an error, the library SHALL let the error reach the caller of the read and SHALL NOT change the dimension.

#### Scenario: Loader fails
- **WHEN** the loader raises an error during a read
- **THEN** the read raises that error and the dimension's root hash is unchanged

### Requirement: Reads that can reach the loader are async
Operations that read a value, a dimension or the keys of a dimension SHALL be `async`. Operations that use only data already in memory, such as comparing the hashes of two values or the root hashes of two dimensions held in memory, SHALL be regular functions.

#### Scenario: Compare two dimensions held in memory
- **WHEN** a user compares the root hashes of two dimensions held in memory
- **THEN** the comparison runs without `await`
