# cache-cleanup Specification

## Purpose

Lets the calling application keep the memory of its process under control by evicting values that nobody has read recently, on a schedule that the application controls.

## Requirements

### Requirement: Cleanup runs only when the application asks
The library SHALL provide a cleanup operation that the application calls. The library SHALL NOT start threads or tasks on its own.

#### Scenario: No cleanup call
- **WHEN** the application never calls cleanup and does not start the interval helper
- **THEN** no value is evicted and the library has started no thread and no task

### Requirement: Record the last read time of each value
The library SHALL record the time of the last read or write of each value held in the in-memory cache.

#### Scenario: Read refreshes the time
- **WHEN** a value was written 50 minutes ago, read 5 minutes ago, and cleanup runs with an idle time of 60 minutes
- **THEN** the value is not evicted

### Requirement: Evict values by idle time
Cleanup SHALL evict from the in-memory cache every value that nobody has read or written for longer than a configurable idle time, 60 minutes by default. Eviction SHALL remove whole values.

#### Scenario: Idle value is evicted
- **WHEN** a value has not been read for 61 minutes and cleanup runs with an idle time of 60 minutes
- **THEN** the in-memory cache no longer holds the value

#### Scenario: Read after eviction with an external cache
- **WHEN** a user reads a value that cleanup evicted and the external cache still holds it
- **THEN** the library fetches it from the external cache and does not call the loader

#### Scenario: Read after eviction without an external cache
- **WHEN** a user reads a value that cleanup evicted, no external cache is configured and a loader is registered
- **THEN** the library calls the loader

### Requirement: Shared nodes stay in memory
Evicting a value SHALL NOT remove nodes that another value still in memory, or a dimension's key map, refers to.

#### Scenario: Evict one of two values that share a node
- **WHEN** two values share a nested dictionary and cleanup evicts only one of them
- **THEN** the other value still reads the nested dictionary without any fetch

### Requirement: Eviction is optional without an external cache
When no external cache is configured, eviction by idle time SHALL be turned off by default and SHALL be possible to turn on.

#### Scenario: Default without an external cache
- **WHEN** no external cache is configured, eviction is not turned on, and a value has not been read for 2 hours
- **THEN** cleanup does not evict the value

### Requirement: Evict values by memory limit
The library SHALL accept an optional memory limit for the in-memory cache. When the estimated memory of the cached values is above the limit, cleanup SHALL evict values in order of least recent read until the estimate is at or below the limit.

#### Scenario: Above the limit
- **WHEN** the estimated memory of cached values is above the configured limit and cleanup runs
- **THEN** cleanup evicts the values read least recently first and stops once the estimate is at or below the limit

### Requirement: Values that no dimension refers to
A value that no dimension refers to any more SHALL stay in the in-memory cache until eviction removes it.

#### Scenario: Key deleted
- **WHEN** a user deletes the only key that referred to a value
- **THEN** the value stays in the in-memory cache until cleanup evicts it by idle time or memory limit

### Requirement: Interval helper
The library SHALL provide an optional helper that runs cleanup at a fixed interval as an `asyncio` task in the application's event loop, and a way to stop it.

#### Scenario: Run cleanup every minute
- **WHEN** the application starts the helper with an interval of 60 seconds
- **THEN** cleanup runs about once every 60 seconds in the application's event loop until the application stops the helper
