# BST deletion

Deleting a key from a BST must keep the BST property. There are three cases.

Deleting a leaf: just remove it (set the parent's pointer to None).

Deleting a node with one child: replace the node with its child. The child's whole subtree moves up one level, and the ordering is preserved.

Deleting a node with two children: you cannot simply put either child in its place, because the other child's subtree would have nowhere valid to go. Instead, replace the node's key with its in-order successor (the smallest key larger than it) or its in-order predecessor (the largest key smaller than it), then delete that successor or predecessor node, which has at most one child.

The in-order successor is the leftmost node of the right subtree: step right once, then go left as far as possible. It is the right child only when that right child has no left subtree.

**Example.** Delete 8 from 8(3(1, 6), 12(10, 14)). The in-order successor is the leftmost node of the right subtree: from 12 go left to 10, which has no left child, so 10 is the successor. Copy 10 into the root and delete the old 10 leaf, giving 10(3(1, 6), 12(_, 14)), which is still a valid BST.
