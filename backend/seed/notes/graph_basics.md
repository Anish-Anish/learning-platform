# Graph representation

A graph is a set of vertices (V) connected by edges (E). Edges can be directed or undirected, weighted or unweighted. Unlike trees, graphs can have cycles and vertices can have many incoming edges.

An adjacency matrix is a V x V grid where cell [u][v] records whether an edge exists. It always uses O(V^2) space, regardless of how many edges exist, but checking whether a specific edge exists is O(1).

An adjacency list stores, for each vertex, a list of its neighbours. It uses O(V + E) space, which is far smaller for sparse graphs (few edges per vertex), the common case for road maps and social networks. Iterating over a vertex's neighbours is fast, which is what BFS and DFS need.

In an undirected graph's adjacency list, each edge {u, v} appears twice: v in u's list and u in v's list. The total length of all lists is 2E.

**Example.** Undirected graph with edges A-B and B-C. Adjacency list: A: [B], B: [A, C], C: [B], with 4 entries for 2 edges. The adjacency matrix is 3 x 3 = 9 cells. For a million vertices with 3 edges each, the matrix needs 10^12 cells while the list needs about 6 million entries.
