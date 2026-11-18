# Hash functions

A hash function maps a key (a string, number, tuple, ...) to an integer, which is then reduced to an array index, for example `hash(key) % table_size`. This lets us jump almost directly to where a key should live.

A hash function must be deterministic: the same key always produces the same hash. Otherwise a value stored under a key could never be found again.

Collisions are unavoidable when there are more possible keys than slots, by the pigeonhole principle. There are infinitely many strings but only, say, 16 slots, so different keys will share an index. A good hash function does not eliminate collisions; it spreads keys uniformly so that collisions are rare and evenly distributed.

Hash functions should also be fast to compute. Equal keys must have equal hashes; unequal keys may or may not.

**Example.** With `h(k) = k % 10`, keys 12 and 22 both map to index 2, which is a collision even though the table may be nearly empty. The function is deterministic: 12 always maps to 2.
