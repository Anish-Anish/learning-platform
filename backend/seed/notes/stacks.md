# Stacks

A stack is a last-in, first-out (LIFO) collection. `push` adds an item to the top and `pop` removes the item from the top, which is always the most recently pushed item still present. `peek` reads the top without removing it.

Push and pop are O(1). A stack can be built on a dynamic array (top = end of the array) or a linked list (top = head).

Popping an empty stack is an underflow error. Correct code checks `is_empty()` before popping; silently returning nothing hides bugs.

Stacks appear everywhere: undo history, matching brackets, evaluating expressions, and the call stack that runs recursive functions. Depth-first search can use an explicit stack instead of recursion.

**Example.** push(1), push(2), push(3), then pop() returns 3 and pop() returns 2. To check brackets in "(())", push on each "(" and pop on each ")". If a ")" arrives when the stack is empty, the brackets are unbalanced.
