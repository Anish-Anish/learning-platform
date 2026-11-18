# Depth-first search

Depth-first search explores a graph by going as deep as possible along one path before backtracking. From a vertex, DFS moves to one unvisited neighbour, then to one of its unvisited neighbours, and so on; only when stuck does it back up and try the next option.

DFS uses a stack, either an explicit stack or, in the recursive version, the call stack. Each recursive call is one step deeper; returning from a call is backtracking.

DFS needs a visited set on graphs with cycles. Without it, following edges around a cycle revisits the same vertices forever. Trees have no cycles, which is why tree traversals don't need one.

With adjacency lists, DFS runs in O(V + E). DFS is the basis for cycle detection, topological sorting and finding connected components.

**Example.** Graph A-B, A-C, B-D, C-D, recursive DFS from A visiting neighbours alphabetically: visit A, go to B, go to D, go to C (D's unvisited neighbour), backtrack all the way. Order: A, B, D, C. BFS would give A, B, C, D, because it finishes a whole level before going deeper.
