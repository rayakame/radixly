# radixly

[![Documentation](https://readthedocs.org/projects/radixly/badge/?version=latest)](https://radixly.rayakame.dev/en/latest/)

Documentation: <https://radixly.rayakame.dev>

## Support

- CPython 3.11+ only. radixly is a hand-written C extension and ships no
  pure-Python fallback.
- Subinterpreters are not supported: on Python 3.12+, importing radixly in a
  subinterpreter raises `ImportError`; on 3.11 the import cannot be refused
  and the behavior is undefined.

## Performance

radixly aims to be the fastest Python implementation of these codecs — and
measures that claim instead of asserting it. Everything below is generated
from the committed record run
([`benchmarks/results/i9-14900KF-performance.json`](benchmarks/results/i9-14900KF-performance.json))
via `python -m benchmarks --render-from benchmarks/results/i9-14900KF-performance.json --inject README.md`;
no number here
is ever typed by hand. Sizes are per-call latency below 64 KiB and sustained
throughput at or above it; “vs reference” is the speedup over the pure-Python
oracle in `tests/reference/`, measured on the same machine in the same run.

<!-- radixly-bench:begin -->
*Measured on Intel(R) Core(TM) i9-14900KF (performance governor), CachyOS, kernel 7.2.3-1-cachyos, CPython 3.13.14, gcc 16.2.1 20260810, radixly 0.1.0.dev0 @ cefe701, 2026-09-08T18:59:26+00:00.*

| codec | direction | 1 B | 200 B | 64 KiB | 1 MiB | vs reference |
|---|---|---|---|---|---|---|
| base32768 | encode | 0.019 μs | 0.114 μs | 1,963 MB/s | 1,963 MB/s | 117x at 200 B |
| base32768 | decode | 0.014 μs | 0.173 μs | 1,275 MB/s | 1,269 MB/s | 127x at 200 B |
| braille | encode | 0.019 μs | 0.168 μs | 1,397 MB/s | 1,404 MB/s | 95x at 200 B |
| braille | decode | 0.016 μs | 0.269 μs | 800 MB/s | 799 MB/s | 77x at 200 B |
| hexagram | encode | 0.019 μs | 0.201 μs | 1,137 MB/s | 1,126 MB/s | 108x at 200 B |
| hexagram | decode | 0.016 μs | 0.328 μs | 616 MB/s | 641 MB/s | 84x at 200 B |
| uro14 | encode | 0.018 μs | 0.118 μs | 2,020 MB/s | 2,007 MB/s | 122x at 200 B |
| uro14 | decode | 0.015 μs | 0.242 μs | 899 MB/s | 896 MB/s | 91x at 200 B |
<!-- radixly-bench:end -->

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="benchmarks/charts/throughput.dark.svg">
  <img src="benchmarks/charts/throughput.svg" alt="Sustained throughput per codec, encode and decode, 1 MiB payloads">
</picture>

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="benchmarks/charts/latency.dark.svg">
  <img src="benchmarks/charts/latency.svg" alt="Per-call latency per codec, encode and decode, 200 B payloads">
</picture>

Per-codec size sweeps (throughput and latency across payload sizes) live in
[`benchmarks/charts/`](benchmarks/charts/), one folder per codec.

To reproduce: `uv run python -m benchmarks` from the repository root — the
suite refuses non-optimized builds, records its own environment (CPU,
governor, compiler, commit), and warns when call floors drift from the
committed baseline.
