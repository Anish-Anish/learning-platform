# Tree terminology

A tree is a hierarchical structure of nodes connected by edges. One node is the root. Every other node has exactly one parent, and a node may have any number of children. A node with no children is a leaf. Because each non-root node has one parent, a tree with n nodes has exactly n - 1 edges and exactly one path from the root to any node.

Depth and height measure different directions. The depth of a node is the number of edges from the root down to that node; the root has depth 0. The height of a node is the number of edges on the longest path from that node down to a leaf; every leaf has height 0. The height of the tree is the height of the root.

A subtree is a node together with all of its descendants. Many tree algorithms work by solving the problem for each child's subtree and combining the answers.

If a node had two parents, there would be two paths to it, and the structure would be a graph, not a tree.

**Example.** In the tree A(B(D, E), C): A is the root (depth 0), B and C have depth 1, D and E have depth 2. Leaves are D, E and C. The height of A is 2, the height of B is 1, and the height of C is 0.
