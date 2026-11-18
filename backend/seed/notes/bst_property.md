# BST ordering property

A binary search tree (BST) is a binary tree where, for every node, every key in the left subtree is less than the node's key, and every key in the right subtree is greater than the node's key.

The property applies to entire subtrees, not just direct children. It is not enough that a node's left child is smaller and its right child is larger. In 10(5(_, 12), 15), each parent-child pair looks ordered (5 < 10, 12 > 5, 15 > 10), but 12 sits in the left subtree of 10 while being larger than 10. This breaks the BST property, and a search for 12 would go right at the root and never find it.

This whole-subtree rule is exactly what makes search work: at each node you can safely discard an entire subtree.

The BST property says nothing about balance. A BST can be perfectly balanced or a long chain. Inserting sorted keys produces a chain that is still a valid BST, just a slow one. Balanced variants such as AVL or red-black trees add extra rules to control height.

**Example.** 8(3(1, 6), 10) is a valid BST: everything left of 8 (3, 1, 6) is smaller than 8, everything right (10) is larger, and the same holds at node 3. Replacing 6 with 9 breaks it, because 9 is in 8's left subtree but greater than 8.
