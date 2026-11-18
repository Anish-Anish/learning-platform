# Hash tables & collisions

A hash table stores key-value entries in an array of buckets. To insert or look up a key, compute its hash, pick the bucket, and search only inside that bucket.

A collision means two different keys map to the same bucket. It does not mean the table is full; collisions can happen when the table is almost empty. A collision strategy decides where the second key goes. With chaining, each bucket holds a small list and colliding keys are appended to it. With open addressing (e.g. linear probing), the second key is placed in the next free slot.

Average lookup is O(1) when keys are spread evenly. The worst case is O(n): if every key lands in the same bucket, a lookup scans one long chain.

The load factor is entries divided by buckets. When it gets too high, the table resizes (typically doubling) and rehashes every key, keeping chains short and average operations O(1).

**Example.** A 10-bucket table with `h(k) = k % 10` and chaining: insert 12 (bucket 2), then 22 (bucket 2 again, a collision). Bucket 2 becomes the chain [12, 22]. The table holds only 2 entries in 10 buckets, so it is far from full.
