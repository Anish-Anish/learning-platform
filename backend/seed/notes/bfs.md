# Breadth-first search

Breadth-first search explores a graph level by level from a start vertex: first the start, then all its neighbours, then their unvisited neighbours, and so on. BFS uses a queue: dequeue a vertex, then enqueue each unvisited neighbour. FIFO order guarantees nearer vertices are processed before farther ones.

BFS marks vertices as visited when they are enqueued. Without a visited set, a graph with cycles makes BFS re-enqueue the same vertices over and over.

Because it explores in order of distance in edges, BFS finds shortest paths by number of edges in unweighted graphs. In a weighted graph, the path with the fewest edges is not necessarily the cheapest one; weighted shortest paths need an algorithm such as Dijkstra's, which uses a priority queue.

With adjacency lists, BFS runs in O(V + E): each vertex is enqueued once and each edge is examined a constant number of times.

**Example.** Graph A-B, A-C, B-D, C-D. BFS from A: visit A; enqueue B and C; dequeue B and enqueue D; dequeue C (D is already visited, so skip it); dequeue D. Order: A, B, C, D. D is found at distance 2 edges.
