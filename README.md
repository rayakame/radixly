<p align="center">
  <a href="https://radixly.rayakame.dev/en/latest/">
    <picture>
      <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/rayakame/radixly/main/docs/_static/logo-wordmark-dark.svg">
      <img src="https://raw.githubusercontent.com/rayakame/radixly/main/docs/_static/logo-wordmark-light.svg" alt="radixly" width="420">
    </picture>
  </a>
</p>

<p align="center">
  <a href="https://radixly.rayakame.dev/en/latest/"><img src="https://readthedocs.org/projects/radixly/badge/?version=latest" alt="Documentation"></a>
  <a href="https://github.com/rayakame/radixly/actions/workflows/ci.yml"><img src="https://github.com/rayakame/radixly/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://github.com/rayakame/radixly/actions/workflows/wheels.yml"><img src="https://github.com/rayakame/radixly/actions/workflows/wheels.yml/badge.svg" alt="Wheels"></a>
  <img src="https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13%20%7C%203.14-blue" alt="Python 3.11 to 3.14">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-green" alt="MIT license"></a>
</p>

Fast binary-to-text codecs for Python. Every codec is a hand-written C
extension behind one small interface: `encode`, `decode` and the size math to
plan around a length limit. Decoding is strict, the package has no
dependencies and ships type stubs.

Documentation: <https://radixly.rayakame.dev/en/latest/>

## Install

```bash
pip install radixly
```

Releases ship wheels for CPython 3.11 to 3.14 on Linux, macOS and Windows.
There is no pure-Python fallback; anywhere else pip builds from source and
needs a C compiler.

## Usage

```python
import radixly

text = radixly.base32768.encode(b"hello")   # str, 3 characters
radixly.base32768.decode(text)              # b'hello'

radixly.base32768.max_bytes(100)            # 187: largest payload that fits 100 characters

try:
    radixly.base32768.decode("hello")
except radixly.DecodeError as error:        # a ValueError with the position
    error.position                          # 0
```

Every codec module has the same four functions; `radixly.get_codec(name)` and
`radixly.CODECS` pick one at runtime.

## Codecs

| codec | bits per char | 100 chars hold | alphabet | catches truncation |
|---|---|---|---|---|
| [base32768](https://radixly.rayakame.dev/en/latest/codecs/base32768.html) | 15 | 187 bytes | qntm's 32,768 BMP code points | no |
| [uro14](https://radixly.rayakame.dev/en/latest/codecs/uro14.html) | 14 | 173 bytes | one CJK block, plus a length prefix | below 16,384 bytes |
| [braille](https://radixly.rayakame.dev/en/latest/codecs/braille.html) | 8 | 100 bytes | 256 Braille patterns | no |
| [hexagram](https://radixly.rayakame.dev/en/latest/codecs/hexagram.html) | 6 | 75 bytes | 64 Yijing hexagrams | partly |

[Choosing a codec](https://radixly.rayakame.dev/en/latest/guides/choosing-a-codec.html) walks through the
trade-offs.

## Performance

Generated from the committed record run by the benchmark suite in
[`benchmarks/`](benchmarks/); no number here is typed by hand. Sizes below
64 KiB show per-call latency, larger ones sustained throughput; "vs reference"
is the speedup over the pure-Python oracle in `tests/reference/`.

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
  <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/rayakame/radixly/main/benchmarks/charts/throughput.dark.svg">
  <img src="https://raw.githubusercontent.com/rayakame/radixly/main/benchmarks/charts/throughput.svg" alt="Sustained throughput per codec, encode and decode, 1 MiB payloads">
</picture>

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/rayakame/radixly/main/benchmarks/charts/latency.dark.svg">
  <img src="https://raw.githubusercontent.com/rayakame/radixly/main/benchmarks/charts/latency.svg" alt="Per-call latency per codec, encode and decode, 200 B payloads">
</picture>

Reproduce with `uv run python -m benchmarks` from the repository root.

## Limits

- CPython only, 3.11 and later.
- No subinterpreters: on 3.12+ the import raises `ImportError` inside one.
  Free-threaded builds import but switch the GIL back on. Details in
  [Subinterpreters and threads](https://radixly.rayakame.dev/en/latest/guides/subinterpreters.html).

## License

MIT, see [LICENSE](LICENSE).
