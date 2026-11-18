# BST search & insert

To search a BST for a key, compare it with the current node: if equal, found; if smaller, go left; if larger, go right. Repeat until found or until you fall off the tree (reach an empty subtree), meaning the key is absent. Because each step discards a whole subtree, search takes O(h) time, where h is the height: O(log n) for a balanced tree, O(n) for a chain.

A recursive search needs a base case for an empty (None) subtree. Without `if node is None: return None`, a search for a missing key eventually calls itself on None and crashes when it reads `None.key`, because recursion does not stop on its own.

Insertion follows the same path as search. Where the search falls off the tree, the new key is attached as a new leaf. Existing nodes do not move, and the new key never goes to the root (unless the tree is empty).

**Example.** Search for 6 in 8(3(1, 7), 10): 6 < 8 go left to 3; 6 > 3 go right to 7; 6 < 7 go left and find None, so it is absent. Inserting 6 places it as the left child of 7. A correct recursive search: `def search(node, k): if node is None: return None; if k == node.key: return node; return search(node.left, k) if k < node.key else search(node.right, k)`.
