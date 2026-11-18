# Pre/in/post-order traversal

A traversal visits every node of a binary tree exactly once in a fixed order. The three depth-first orders differ only in when the node itself is visited relative to its subtrees.

Pre-order visits the node first, then the left subtree, then the right subtree (node, left, right). It is useful for copying a tree or printing its structure.

In-order visits the left subtree, then the node, then the right subtree (left, node, right). In a binary search tree, in-order traversal produces the keys in sorted ascending order, because every key in the left subtree is smaller than the node and every key in the right subtree is larger.

Post-order visits the left subtree, then the right subtree, then the node (left, right, node). It is useful for deleting a tree or computing sizes, since children are handled before their parent.

Traversals are naturally recursive: each call handles one node and recurses into the subtrees, relying on the call stack to come back up. The base case is an empty (None) subtree.

**Example.** For the BST 8(3(1, 6), 10): pre-order gives 8, 3, 1, 6, 10; in-order gives 1, 3, 6, 8, 10 (sorted); post-order gives 1, 6, 3, 10, 8.
