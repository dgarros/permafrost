
The Permaforst library extend Pydantic object to support immutable nested data-classes that can be easily compared, updated and stored efficiently and that are immutable by default

Each class automatically calculate a hash that will be stored to ensure efficient comparison with other objects.

Merge
- deep merge by default
- Option 1 : replace list
- Option 2 : merge list
- Option 3 : incremental update list (not sure how to manage that today)

By default we will not manage state, and eventually we couldh have a derivative of the class that will support state

Diff
Comparing 2 permafrost object should return a clear diff


In order for the storage to be efficient, the permafrost library should include a registry that will take care of storing the object efficiently based on their hash
