# Big-O complexity

Big-O describes how an algorithm's running time (or memory) grows as the input size n grows. It is a statement about the growth rate as an upper bound, not an exact count of steps or seconds.

Constant factors and lower-order terms are dropped. An algorithm doing 2n + 5 steps is O(n); one doing 3n^2 + 100n steps is O(n^2). O(2n) and O(n) are the same class: if n doubles, both double. Constants matter in practice but do not change the complexity class.

Common classes, from fastest-growing-slowest: O(1) constant, O(log n) logarithmic, O(n) linear, O(n log n), O(n^2) quadratic. A loop that halves n each iteration (as in binary search) runs about log2 n times, so it is O(log n), not O(n). A loop inside another loop, each over the input, usually gives O(n^2).

To find the Big-O of code, count how the number of basic steps grows with n and keep only the dominant term.

**Example.** `while n > 1: n = n // 2` starting from n = 1024 runs 10 times (1024 to 512 to ... to 1). Doubling n to 2048 adds just one more step, which is the signature of O(log n). A loop `for i in range(n): for j in range(n):` does n * n steps, which is O(n^2).
