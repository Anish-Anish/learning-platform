# Variables, memory & references

A variable is a name bound to a value stored somewhere in memory. For simple values such as small integers this feels like the variable "is" the value, but for objects such as lists, nodes or dictionaries the variable holds a reference: the address of the object, not the object itself.

Assignment of an object copies the reference, not the object. After `b = a`, both names refer to the same list in memory. Mutating the list through `b` (for example `b.append(4)`) is visible through `a`, because there is only one list. Making a real copy requires an explicit operation such as `a.copy()` or `list(a)`.

Passing an object to a function passes a reference too. The parameter inside the function points at the caller's object, so mutating it inside the function changes what the caller sees. Rebinding the parameter (`lst = []`) only changes the local name and does not affect the caller.

References are the foundation of every linked structure in this course: a linked-list node stores a reference to the next node, and a tree node stores references to its children. Following a reference is how we move from one node to another.

**Example.** `a = [1, 2, 3]; b = a; b.append(4); print(a)` prints `[1, 2, 3, 4]` because `a` and `b` are two names for one list. With `b = a.copy()` instead, `a` would still print `[1, 2, 3]`.
