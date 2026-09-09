*Measured on Intel(R) Core(TM) i9-14900KF (performance governor), CachyOS, kernel 7.2.3-1-cachyos, CPython 3.13.14, gcc 16.2.1 20260810, radixly 0.1.0.dev0 @ cefe701, 2026-09-08T18:59:26+00:00.*

| codec | direction | 1 B | 200 B | 64 KiB | 1 MiB | vs reference |
|---|---|---|---|---|---|---|
| uro14 | encode | 0.018 μs | 0.118 μs | 2,020 MB/s | 2,007 MB/s | 122x at 200 B |
| uro14 | decode | 0.015 μs | 0.242 μs | 899 MB/s | 896 MB/s | 91x at 200 B |

```{image} ../../benchmarks/charts/uro14/throughput.svg
:alt: uro14 sustained throughput
:class: only-light
```

```{image} ../../benchmarks/charts/uro14/throughput.dark.svg
:alt: uro14 sustained throughput
:class: only-dark
```

```{image} ../../benchmarks/charts/uro14/latency.svg
:alt: uro14 per-call latency
:class: only-light
```

```{image} ../../benchmarks/charts/uro14/latency.dark.svg
:alt: uro14 per-call latency
:class: only-dark
```
