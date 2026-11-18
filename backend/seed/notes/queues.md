# Queues

A queue is a first-in, first-out (FIFO) collection. `enqueue` adds an item at the back; `dequeue` removes the item at the front, which is the item that has waited longest. It works like a line at a ticket counter.

A naive array queue that removes index 0 and shifts everything is O(n) per dequeue. That is avoidable. A circular buffer keeps a front index and a back index in a fixed array and simply moves the front index forward (wrapping around), so enqueue and dequeue are O(1). A linked list with head and tail references also gives O(1) for both.

Queues model waiting lines, printer jobs and task scheduling, and they are the engine of breadth-first search, which processes nodes in the order they were discovered.

**Example.** enqueue(A), enqueue(B), enqueue(C), then dequeue() returns A (it arrived first), then B. In a circular buffer of size 4 holding [A, B, C, _] with front = 0, dequeue returns A and sets front = 1, so no element moves.
