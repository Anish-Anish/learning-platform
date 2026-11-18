# Recursion: base case & recursive case

A recursive function solves a problem by calling itself on a smaller version of the same problem. Every correct recursive function has two parts: a base case and a recursive case.

The base case is the smallest version of the problem, answered directly without another recursive call. It is what stops the recursion. For factorial the base case is `n == 0`, which returns 1. For a tree or list it is usually the empty case: a `None` node or an empty list.

The recursive case breaks the problem into a smaller subproblem and calls the function on it, then combines the result: `fact(n) = n * fact(n - 1)`.

Recursion does not stop by itself. Without a base case, nothing ever returns: each call makes another call until the program runs out of stack space (a stack overflow), or it crashes earlier by touching an invalid value such as `None.left`.

Each recursive call must make progress toward the base case. If `f(n)` calls `f(n)` or `f(n + 1)` when the base case is `n == 0`, the base case is never reached, even though it exists.

**Example.** `def countdown(n): if n == 0: return; print(n); countdown(n - 1)`. Calling `countdown(3)` prints 3, 2, 1 and stops at the base case. Remove the `if n == 0: return` line and it prints 3, 2, 1, 0, -1, -2, ... until a RecursionError.
