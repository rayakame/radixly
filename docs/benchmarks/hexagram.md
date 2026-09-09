*Measured on Intel(R) Core(TM) i9-14900KF (performance governor), CachyOS, kernel 7.2.3-1-cachyos, CPython 3.13.14, gcc 16.2.1 20260810, radixly 0.1.0.dev0 @ cefe701, 2026-09-08T18:59:26+00:00.*

| codec | direction | 1 B | 200 B | 64 KiB | 1 MiB | vs reference |
|---|---|---|---|---|---|---|
| hexagram | encode | 0.019 μs | 0.201 μs | 1,137 MB/s | 1,126 MB/s | 108x at 200 B |
| hexagram | decode | 0.016 μs | 0.328 μs | 616 MB/s | 641 MB/s | 84x at 200 B |

```{image} ../../benchmarks/charts/hexagram/throughput.svg
:alt: hexagram sustained throughput
:class: only-light
```

```{image} ../../benchmarks/charts/hexagram/throughput.dark.svg
:alt: hexagram sustained throughput
:class: only-dark
```

```{image} ../../benchmarks/charts/hexagram/latency.svg
:alt: hexagram per-call latency
:class: only-light
```

```{image} ../../benchmarks/charts/hexagram/latency.dark.svg
:alt: hexagram per-call latency
:class: only-dark
```
