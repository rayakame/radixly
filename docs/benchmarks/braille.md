*Measured on Intel(R) Core(TM) i9-14900KF (performance governor), CachyOS, kernel 7.2.3-1-cachyos, CPython 3.13.14, gcc 16.2.1 20260810, radixly 0.1.0.dev0 @ cefe701, 2026-09-08T18:59:26+00:00.*

| codec | direction | 1 B | 200 B | 64 KiB | 1 MiB | vs reference |
|---|---|---|---|---|---|---|
| braille | encode | 0.019 μs | 0.168 μs | 1,397 MB/s | 1,404 MB/s | 95x at 200 B |
| braille | decode | 0.016 μs | 0.269 μs | 800 MB/s | 799 MB/s | 77x at 200 B |

```{image} /benchmarks/charts/braille/throughput.svg
:alt: braille sustained throughput
:class: only-light
```

```{image} /benchmarks/charts/braille/throughput.dark.svg
:alt: braille sustained throughput
:class: only-dark
```

```{image} /benchmarks/charts/braille/latency.svg
:alt: braille per-call latency
:class: only-light
```

```{image} /benchmarks/charts/braille/latency.dark.svg
:alt: braille per-call latency
:class: only-dark
```
