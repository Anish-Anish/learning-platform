# Binary trees

A binary tree is a tree in which each node has at most two children, called left and right. A node can have zero, one or two children. Each child is itself the root of a subtree, which makes binary trees naturally recursive.

Shape varies a lot. A balanced binary tree with n nodes has height about log2 n. But a binary tree can also be a degenerate chain where every node has only one child; then its height is n - 1. So "binary tree" alone does not guarantee short height.

Special shapes have names: a full binary tree has every node with 0 or 2 children; a complete binary tree fills every level left to right except possibly the last; a perfect tree has all leaves on the same level. These are special cases, not the rule.

Many algorithms process the left subtree, the right subtree and the node itself recursively: counting nodes, computing height, and the traversals.

**Example.** Inserting keys 1, 2, 3, 4 into an empty binary search tree produces 1 -> 2 -> 3 -> 4 down the right side, a valid binary tree of 4 nodes with height 3, not log2 4 = 2.
