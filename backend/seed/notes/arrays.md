# Arrays & indexing

An array stores its elements contiguously: one after another in a single block of memory, each the same size. This layout is what makes arrays fast to index.

Indices start at 0. An array of n elements has valid indices 0 to n-1, so the last element is at index n-1. Reading index n is an out-of-bounds error.

Access by index is O(1). The address of element i is computed with address arithmetic: `address = base + i * element_size`. The computer jumps straight there without visiting earlier elements, so reading `a[0]` and `a[999999]` costs the same.

Appending to the end of a dynamic array is O(1) on average. Inserting or deleting at the front or in the middle is O(n), because every element after the position must shift one slot to keep the block contiguous. Inserting at index 0 of an n-element array moves all n elements.

**Example.** For `a = [10, 20, 30, 40]`, `a[0]` is 10 and the last element is `a[3]` (n-1 = 3). Inserting 5 at index 0 shifts 10, 20, 30 and 40 one slot right, which is 4 moves, so the cost grows linearly with n.
