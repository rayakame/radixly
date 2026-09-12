<p align="center">
  <a href="https://radixly.rayakame.dev/en/latest/">
    <picture>
      <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/rayakame/radixly/main/docs/_static/logo-wordmark-dark.svg">
      <img src="https://raw.githubusercontent.com/rayakame/radixly/main/docs/_static/logo-wordmark-light.svg" alt="radixly" width="420">
    </picture>
  </a>
</p>

<p align="center">
  <a href="https://pypi.org/project/radixly/"><img src="https://img.shields.io/pypi/v/radixly" alt="PyPI"></a>
  <a href="https://radixly.rayakame.dev/en/latest/"><img src="https://readthedocs.org/projects/radixly/badge/?version=latest" alt="Documentation"></a>
  <a href="https://github.com/rayakame/radixly/actions/workflows/ci.yml"><img src="https://github.com/rayakame/radixly/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://github.com/rayakame/radixly/actions/workflows/wheels.yml"><img src="https://github.com/rayakame/radixly/actions/workflows/wheels.yml/badge.svg" alt="Wheels"></a>
  <a href="https://pypi.org/project/radixly/"><img src="https://img.shields.io/pypi/pyversions/radixly" alt="Python versions"></a>
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
| [base65536](https://radixly.rayakame.dev/en/latest/codecs/base65536.html) | 16 | 200 bytes | qntm's 257 blocks, most of them astral | no |
| [base32768](https://radixly.rayakame.dev/en/latest/codecs/base32768.html) | 15 | 187 bytes | qntm's 32,768 BMP code points | no |
| [base2048](https://radixly.rayakame.dev/en/latest/codecs/base2048.html) | 11 | 137 bytes | qntm's 2,048 letters and numerals below U+1100 | no |
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
*Measured on Intel(R) Core(TM) i9-14900KF (performance governor), CachyOS, kernel 7.2.4-3-cachyos, CPython 3.14.6, gcc 16.2.1 20260810, radixly 1.0.0 @ 2ed42e1, 2026-09-12T21:10:47+00:00.*

| codec | direction | 1 B | 200 B | 64 KiB | 1 MiB | vs reference |
|---|---|---|---|---|---|---|
| base16 | encode | 0.017 μs | 0.089 μs | 3,007 MB/s | 3,014 MB/s | 94x at 200 B |
| base16 | decode | 0.014 μs | 0.129 μs | 1,817 MB/s | 1,815 MB/s | 136x at 200 B |
| base16 (stdlib base64 3.14.6) | encode | 0.066 μs | 0.232 μs | 1,289 MB/s | 1,284 MB/s | — |
| base16 (stdlib base64 3.14.6) | decode | 0.109 μs | 0.384 μs | 752 MB/s | 551 MB/s | — |
| base32 | encode | 0.020 μs | 0.084 μs | 3,022 MB/s | 3,029 MB/s | 327x at 200 B |
| base32 | decode | 0.022 μs | 0.152 μs | 1,526 MB/s | 1,522 MB/s | 164x at 200 B |
| base32 (stdlib base64 3.14.6) | encode | 0.548 μs | 7.896 μs | 26 MB/s | 26 MB/s | — |
| base32 (stdlib base64 3.14.6) | decode | 0.567 μs | 11.130 μs | 18 MB/s | 18 MB/s | — |
| base32hex | encode | 0.020 μs | 0.084 μs | 3,052 MB/s | 3,049 MB/s | 326x at 200 B |
| base32hex | decode | 0.022 μs | 0.151 μs | 1,523 MB/s | 1,525 MB/s | 163x at 200 B |
| base32hex (stdlib base64 3.14.6) | encode | 0.544 μs | 7.878 μs | 26 MB/s | 26 MB/s | — |
| base32hex (stdlib base64 3.14.6) | decode | 0.567 μs | 11.171 μs | 18 MB/s | 18 MB/s | — |
| base2048 | encode | 0.019 μs | 0.133 μs | 1,678 MB/s | 1,676 MB/s | 108x at 200 B |
| base2048 | decode | 0.015 μs | 0.235 μs | 902 MB/s | 902 MB/s | 98x at 200 B |
| base2048 (PyPI base2048 0.1.3, other alphabet) | encode | 0.102 μs | 1.028 μs | 138 MB/s | 131 MB/s | — |
| base2048 (PyPI base2048 0.1.3, other alphabet) | decode | 0.099 μs | 0.869 μs | 124 MB/s | 114 MB/s | — |
| base32768 | encode | 0.019 μs | 0.114 μs | 1,939 MB/s | 1,951 MB/s | 108x at 200 B |
| base32768 | decode | 0.015 μs | 0.187 μs | 1,148 MB/s | 1,155 MB/s | 106x at 200 B |
| base65536 | encode | 0.020 μs | 0.047 μs | 6,445 MB/s | 6,819 MB/s | 185x at 200 B |
| base65536 | decode | 0.021 μs | 0.066 μs | 4,289 MB/s | 4,285 MB/s | 155x at 200 B |
| base65536 (PyPI base65536 0.1.1) | encode | 0.210 μs | 8.063 μs | 23 MB/s | 23 MB/s | — |
| base65536 (PyPI base65536 0.1.1) | decode | 0.160 μs | 12.291 μs | 17 MB/s | 17 MB/s | — |
| braille | encode | 0.020 μs | 0.172 μs | 1,360 MB/s | 1,354 MB/s | 90x at 200 B |
| braille | decode | 0.016 μs | 0.277 μs | 777 MB/s | 777 MB/s | 68x at 200 B |
| hexagram | encode | 0.020 μs | 0.205 μs | 1,121 MB/s | 1,128 MB/s | 100x at 200 B |
| hexagram | decode | 0.017 μs | 0.327 μs | 654 MB/s | 646 MB/s | 73x at 200 B |
| uro14 | encode | 0.019 μs | 0.124 μs | 1,858 MB/s | 1,928 MB/s | 104x at 200 B |
| uro14 | decode | 0.015 μs | 0.189 μs | 983 MB/s | 995 MB/s | 99x at 200 B |
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
