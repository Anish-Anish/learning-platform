# Binary heaps

A binary heap is a complete binary tree with the heap property. In a min-heap, every parent is less than or equal to its children, so the minimum is always at the root. A max-heap is the mirror image.

A heap is only partially ordered, not sorted. The heap property relates parents to children only; siblings and nodes on the same level can be in any order. [1, 5, 2, 6, 7, 3] is a valid min-heap but not a sorted array.

Because the tree is complete, it is stored compactly in an array: the node at index i has children at 2i + 1 and 2i + 2 and its parent at (i - 1) // 2.

Insert appends the new element at the end of the array and then sifts it up, swapping with its parent while it is smaller, which is O(log n). Extract-min removes the root, moves the last element to the root, and sifts it down, swapping with the smaller child, which is O(log n). Peeking at the minimum is O(1).

**Example.** Insert 0 into min-heap [1, 3, 2]: append to get [1, 3, 2, 0]; 0's parent is 3 (index 1), so swap to [1, 0, 2, 3]; its parent is now 1 (index 0), so swap to [0, 1, 2, 3]. Two swaps for a tree of height 2.
