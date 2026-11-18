"""Hand-labelled datasets for evals (§15.2).

TEACH_LABELLED: student explanations with a reference score (0-100) assigned by a human grader against
the concept's key points. Used to measure teach-the-bot scorer agreement.
"""

from __future__ import annotations

TEACH_LABELLED: list[dict] = [
    {
        "concept_id": "stacks",
        "text": "A stack is last in first out. You push things onto the top and pop them off the top, and both "
        "of those are O(1). If you pop when it's empty you get an underflow error, so check is_empty first.",
        "reference": 100,
    },
    {
        "concept_id": "stacks",
        "text": "A stack is like a line at the bank: the first person in gets served first.",
        "reference": 10,
    },
    {
        "concept_id": "queues",
        "text": "Queues are first in, first out. You enqueue at the back and dequeue from the front.",
        "reference": 50,
    },
    {
        "concept_id": "bst_property",
        "text": "Every key in the left subtree has to be less than the node and every key in the right subtree "
        "greater, and that applies to the entire subtree, not just the children. A BST doesn't have to be balanced.",
        "reference": 100,
    },
    {
        "concept_id": "bst_property",
        "text": "The left child is smaller than the node and the right child is bigger.",
        "reference": 35,
    },
    {
        "concept_id": "recursion_base",
        "text": "Recursion is when a function calls itself on a smaller subproblem. The base case stops the "
        "recursion and returns directly; without a base case it never stops and the stack overflows.",
        "reference": 75,
    },
    {
        "concept_id": "hash_tables",
        "text": "A hash table stores entries in buckets chosen by the hash. A collision means two keys map to the "
        "same bucket, not that the table is full, and chaining resolves it.",
        "reference": 60,
    },
    {
        "concept_id": "linked_lists",
        "text": "Each node stores a value and a reference to the next node. To get the k-th element you walk "
        "from the head.",
        "reference": 50,
    },
]
