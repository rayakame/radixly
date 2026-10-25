# Drop-in performance

All 22 functions run in C. What that buys depends on what the standard library
already had: where it runs a Python loop the port replaces the loop, where it
wraps `binascii` the port only removes the wrapper, and on the two file-object
functions the port is slower on purpose. {doc}`index` has the contract these
numbers sit on, and the short answer on whether to swap.

:::{note}
Preview numbers, not a regression gate. The powersave governor and a dirty tree
disqualify this run as a record, so trust the shape and not the digits. The
committed record in `benchmarks/results/` covers the strict codecs, not these
22 functions.
:::

*Measured on Intel(R) Core(TM) i9-14900KF (powersave governor), CachyOS, kernel
7.2.6-1-cachyos, CPython 3.14.6, gcc 16.2.1 20260810, optimized build, best of
seven, 2026-09-19.*

## All 22 functions

Sorted by the gain at 64 KiB, which sorts the three groups on its own. The 200 B
columns are per-call latency, the 64 KiB columns sustained throughput, and the
gain is the standard library's figure over the drop-in's, so below 1 the drop-in
is slower.

| function | group | 200 B stdlib | 200 B drop-in | 64 KiB stdlib | 64 KiB drop-in | gain at 64 KiB |
|---|---|---|---|---|---|---|
| `a85decode` | loop | 12.884 μs | 0.182 μs | 16 MB/s | 1,854 MB/s | 115x |
| `b32hexencode` | loop | 7.802 μs | 0.091 μs | 26 MB/s | 3,014 MB/s | 114x |
| `b32encode` | loop | 7.747 μs | 0.089 μs | 27 MB/s | 3,032 MB/s | 112x |
| `b85decode` | loop | 7.861 μs | 0.100 μs | 27 MB/s | 2,601 MB/s | 97x |
| `z85decode` | loop | 7.737 μs | 0.101 μs | 26 MB/s | 2,545 MB/s | 96x |
| `b32decode` | loop | 10.918 μs | 0.135 μs | 20 MB/s | 1,735 MB/s | 88x |
| `b32hexdecode` | loop | 10.999 μs | 0.134 μs | 19 MB/s | 1,706 MB/s | 88x |
| `a85encode` | loop | 5.543 μs | 0.123 μs | 40 MB/s | 2,195 MB/s | 55x |
| `z85encode` | loop | 5.435 μs | 0.120 μs | 41 MB/s | 2,212 MB/s | 55x |
| `b85encode` | loop | 5.524 μs | 0.122 μs | 41 MB/s | 2,215 MB/s | 54x |
| `encodebytes` | wrapper | 0.557 μs | 0.111 μs | 556 MB/s | 3,270 MB/s | 5.88x |
| `urlsafe_b64encode` | wrapper | 0.263 μs | 0.078 μs | 1,078 MB/s | 3,577 MB/s | 3.32x |
| `standard_b64encode` | wrapper | 0.191 μs | 0.079 μs | 1,472 MB/s | 3,501 MB/s | 2.38x |
| `b64encode` | wrapper | 0.183 μs | 0.078 μs | 1,465 MB/s | 3,479 MB/s | 2.37x |
| `b16encode` | wrapper | 0.180 μs | 0.088 μs | 1,435 MB/s | 3,050 MB/s | 2.13x |
| `urlsafe_b64decode` | wrapper | 0.365 μs | 0.200 μs | 909 MB/s | 1,296 MB/s | 1.43x |
| `b16decode` | wrapper | 0.381 μs | 0.233 μs | 795 MB/s | 1,085 MB/s | 1.36x |
| `standard_b64decode` | wrapper | 0.260 μs | 0.202 μs | 1,192 MB/s | 1,289 MB/s | 1.08x |
| `b64decode` | wrapper | 0.252 μs | 0.202 μs | 1,174 MB/s | 1,255 MB/s | 1.07x |
| `decodebytes` | wrapper | 0.327 μs | 0.259 μs | 942 MB/s | 983 MB/s | 1.04x |
| `encode` | file | 0.535 μs | 0.782 μs | 554 MB/s | 444 MB/s | 0.80x |
| `decode` | file | 0.519 μs | 0.953 μs | 521 MB/s | 298 MB/s | 0.57x |

At 200 B the same three groups run 45x to 87x, 1.25x to 5.03x, and 0.54x to
0.68x. Both sides ran on CPython 3.14.6, where the standard library has
`z85encode` and `z85decode`.

## Why the loops are so slow

The standard library works per group or per byte:

- `_b32encode` walks the payload in 5-byte groups, four lookups into a
  1,024-entry table per group.
- `_85encode` unpacks the payload with `struct` and builds each word from three
  lookups.
- `z85encode` adds a `translate` over the `b85` result, and `z85decode` one over
  its input before the `b85` loop sees it.
- `a85decode` walks its input one byte at a time: the slowest function on the
  list at 16 MB/s, and the largest gain at 115x.

## Why the wrappers gain so little

Where `binascii` already does the work, the gain is whatever the Python around
the call costs, and it tracks it closely:

| function | what the standard library adds around `binascii` | gain at 64 KiB |
|---|---|---|
| `decodebytes` | a type check and one `a2b_base64` call | 1.04x |
| `b64decode` | an `altchars` check | 1.07x |
| `b64encode` | an `altchars` check | 2.37x |
| `urlsafe_b64encode` | a `translate` over the result | 3.32x |
| `encodebytes` | 57-byte chunks sliced in Python, one `b2a_base64` per chunk | 5.88x |

Decoding gains least of all, because `a2b_base64` already does nearly the whole
of it. A `b64decode`-heavy workload gets 1.07x at 64 KiB, which is no reason on
its own to change an import.

## Why the file pair is slower

`encode` and `decode` take binary file objects, and the port loses on both,
0.80x and 0.57x at 64 KiB. Fidelity costs it. The standard library reads 57
bytes at a time, tops up a short read, and writes one line per chunk, while
`decode` calls `readline` and writes what each line decodes to. The port makes
the same calls in the same order, because a file object that counts its reads
would otherwise see a different module. Reading in larger pieces would be
faster, and the file object would see the difference.

Reproduce any of this with the benchmark suite in the repository:
`uv run python -m benchmarks`.
