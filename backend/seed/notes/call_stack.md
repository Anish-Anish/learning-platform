# Recursion & the call stack

Every time a function is called, the runtime pushes a new stack frame onto the call stack. The frame holds that call's parameters, its local variables and the place to return to.

Each frame has its own copy of parameters and local variables. In a recursive function, `fact(3)`, `fact(2)` and `fact(1)` are three separate frames, each with its own `n`. Changing `n` in one frame does not change `n` in another. This is why `return n * fact(n - 1)` works: after the inner call returns, the outer frame still has its own `n`.

When a call returns, its frame is popped and control goes back to the immediate caller, which resumes where it left off and may do more work (like the multiplication) before returning itself. Results flow back up one frame at a time; the deepest call does not jump straight back to the original caller.

The call stack has limited size. Very deep recursion (or recursion without a working base case) causes a stack overflow.

**Example.** `fact(3)` pushes frames fact(3) to fact(2) to fact(1) to fact(0). fact(0) returns 1 to fact(1), which computes 1 * 1 = 1 and returns to fact(2), which computes 2 * 1 = 2 and returns to fact(3), which computes 3 * 2 = 6. Each multiplication uses that frame's own n.
