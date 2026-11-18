# Priority queues

A priority queue is a collection where each item has a priority, and remove always returns the highest-priority item (for a min-priority queue, the smallest key), not the oldest item. Arrival order does not matter, unlike a regular FIFO queue.

The usual implementation is a binary heap: insert and remove-min are both O(log n), and peek is O(1).

Other implementations trade costs. An unsorted array gives O(1) insert but O(n) remove-min (scan for the minimum). A sorted array gives O(1) remove-min but O(n) insert, because elements must shift to keep it sorted. Over many mixed operations, the heap's O(log n) for both wins.

Priority queues power task schedulers, event simulations, Huffman coding and Dijkstra's shortest-path algorithm.

**Example.** Insert tasks with priorities 5, 1, 3 into a min-priority queue. remove() returns 1, then 3, then 5, even though 5 arrived first. Inserting 4 into the sorted array [1, 3, 5, 7, 9] shifts 5, 7 and 9, which is O(n) work.
