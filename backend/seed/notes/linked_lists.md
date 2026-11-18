# Linked lists

A linked list is a chain of nodes. Each node stores a value and a reference to the next node; the last node's next is `None`. The list itself is just a reference to the first node, the head.

Nodes are not contiguous in memory, so there is no address formula for the k-th node. Access to the k-th element requires walking from the head and following k next pointers, which is O(k). Searching for a value is O(n).

The strength of linked lists is cheap relinking. Inserting or deleting at a known node is O(1): only a couple of pointers change and nothing shifts. Inserting at the head is always O(1).

Deleting a node requires updating the previous node's next pointer to skip over it: for A -> B -> C, deleting B means setting `A.next = B.next` (which is C). If you only "remove" B without relinking, A still points at B and the list is unchanged.

**Example.** To insert X after node A in A -> B: set `X.next = A.next` (B), then `A.next = X`, giving A -> X -> B, two pointer changes regardless of list length. To read the 1000th value you must follow 999 next pointers from the head.
