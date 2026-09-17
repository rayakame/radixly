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
| [base32768](https://radixly.rayakame.dev/en/latest/codecs/base32768.html) | 15 | 187 bytes | qntm's 32,768 BMP code points | partly |
| [base2048](https://radixly.rayakame.dev/en/latest/codecs/base2048.html) | 11 | 137 bytes | qntm's 2,048 letters and numerals below U+1100 | partly |
| [uro14](https://radixly.rayakame.dev/en/latest/codecs/uro14.html) | 14 | 173 bytes | one CJK block, plus a length prefix | below 16,384 bytes |
| [braille](https://radixly.rayakame.dev/en/latest/codecs/braille.html) | 8 | 100 bytes | 256 Braille patterns | no |
| [hexagram](https://radixly.rayakame.dev/en/latest/codecs/hexagram.html) | 6 | 75 bytes | 64 Yijing hexagrams | partly |
| [base64](https://radixly.rayakame.dev/en/latest/codecs/base64.html) | 6 | 75 bytes | RFC 4648: `A` to `Z`, `a` to `z`, `0` to `9`, `+`, `/`, `=` padding | partly |
| [base64url](https://radixly.rayakame.dev/en/latest/codecs/base64url.html) | 6 | 75 bytes | RFC 4648: base64 with `-` and `_` for `+` and `/`, `=` padding | partly |
| [base32](https://radixly.rayakame.dev/en/latest/codecs/base32.html) | 5 | 60 bytes | RFC 4648: `A` to `Z`, `2` to `7`, `=` padding | partly |
| [base32hex](https://radixly.rayakame.dev/en/latest/codecs/base32hex.html) | 5 | 60 bytes | RFC 4648: `0` to `9`, `A` to `V`, `=` padding | partly |
| [base16](https://radixly.rayakame.dev/en/latest/codecs/base16.html) | 4 | 50 bytes | RFC 4648: 16 uppercase hexadecimal digits | no |

"partly" means most cuts raise but a cut at the right place passes; "no" means
half or more of the cuts pass.

[Choosing a codec](https://radixly.rayakame.dev/en/latest/guides/choosing-a-codec.html) walks through the
trade-offs.

## Standard library drop-in

`radixly.compat.base64` is the standard library's `base64` with the same names,
arguments, results and errors; the `b16`, `b32`, `b32hex` and `b64` families
(`b64encode`, `b64decode`, `standard_b64encode`, `standard_b64decode`,
`urlsafe_b64encode` and `urlsafe_b64decode` among them) run in C, the rest are
the standard library's own until ported. CPython's own `test_base64` suite runs
against it. See [the drop-in page](https://radixly.rayakame.dev/en/latest/compat.html).

## Performance

Generated from the committed record run by the benchmark suite in
[`benchmarks/`](benchmarks/); no number here is typed by hand. Sizes below
64 KiB show per-call latency, larger ones sustained throughput; "vs reference"
is the speedup over the pure-Python oracle in `tests/reference/`.

<!-- radixly-bench:begin -->
*Measured on Intel(R) Core(TM) i9-14900KF (performance governor), CachyOS, kernel 7.2.4-3-cachyos, CPython 3.14.6, gcc 16.2.1 20260810, radixly 1.0.0 @ 632331f, 2026-09-17T17:58:09+00:00.*

| codec | direction | 1 B | 200 B | 64 KiB | 1 MiB | vs reference |
|---|---|---|---|---|---|---|
| base16 | encode | 0.017 μs | 0.086 μs | 3,101 MB/s | 3,101 MB/s | 93x at 200 B |
| base16 | decode | 0.014 μs | 0.127 μs | 1,862 MB/s | 1,856 MB/s | 134x at 200 B |
| base16 (stdlib base64 3.14.6) | encode | 0.067 μs | 0.226 μs | 1,330 MB/s | 1,319 MB/s | — |
| base16 (stdlib base64 3.14.6) | decode | 0.106 μs | 0.374 μs | 771 MB/s | 568 MB/s | — |
| base32 | encode | 0.019 μs | 0.085 μs | 3,094 MB/s | 3,096 MB/s | 323x at 200 B |
| base32 | decode | 0.023 μs | 0.149 μs | 1,557 MB/s | 1,564 MB/s | 167x at 200 B |
| base32 (stdlib base64 3.14.6) | encode | 0.536 μs | 8.134 μs | 26 MB/s | 26 MB/s | — |
| base32 (stdlib base64 3.14.6) | decode | 0.553 μs | 11.708 μs | 18 MB/s | 19 MB/s | — |
| base32hex | encode | 0.020 μs | 0.084 μs | 3,098 MB/s | 3,106 MB/s | 319x at 200 B |
| base32hex | decode | 0.023 μs | 0.150 μs | 1,555 MB/s | 1,562 MB/s | 167x at 200 B |
| base32hex (stdlib base64 3.14.6) | encode | 0.537 μs | 7.737 μs | 27 MB/s | 26 MB/s | — |
| base32hex (stdlib base64 3.14.6) | decode | 0.580 μs | 11.505 μs | 18 MB/s | 18 MB/s | — |
| base64 | encode | 0.019 μs | 0.078 μs | 3,535 MB/s | 3,533 MB/s | 361x at 200 B |
| base64 | decode | 0.022 μs | 0.133 μs | 1,871 MB/s | 1,868 MB/s | 191x at 200 B |
| base64 (stdlib base64 3.14.6) | encode | 0.071 μs | 0.222 μs | 1,392 MB/s | 1,366 MB/s | — |
| base64 (stdlib base64 3.14.6) | decode | 0.072 μs | 0.254 μs | 1,176 MB/s | 1,139 MB/s | — |
| base64url | encode | 0.019 μs | 0.078 μs | 3,523 MB/s | 3,544 MB/s | 361x at 200 B |
| base64url | decode | 0.022 μs | 0.133 μs | 1,866 MB/s | 1,874 MB/s | 189x at 200 B |
| base64url (stdlib base64 3.14.6) | encode | 0.097 μs | 0.305 μs | 1,033 MB/s | 1,011 MB/s | — |
| base64url (stdlib base64 3.14.6) | decode | 0.141 μs | 0.377 μs | 893 MB/s | 882 MB/s | — |
| base2048 | encode | 0.019 μs | 0.128 μs | 1,781 MB/s | 1,772 MB/s | 108x at 200 B |
| base2048 | decode | 0.015 μs | 0.229 μs | 934 MB/s | 938 MB/s | 98x at 200 B |
| base2048 (PyPI base2048 0.1.3, other alphabet) | encode | 0.101 μs | 0.994 μs | 146 MB/s | 139 MB/s | — |
| base2048 (PyPI base2048 0.1.3, other alphabet) | decode | 0.095 μs | 0.841 μs | 130 MB/s | 121 MB/s | — |
| base32768 | encode | 0.019 μs | 0.110 μs | 2,007 MB/s | 2,008 MB/s | 107x at 200 B |
| base32768 | decode | 0.015 μs | 0.182 μs | 1,198 MB/s | 1,206 MB/s | 107x at 200 B |
| base65536 | encode | 0.019 μs | 0.044 μs | 7,135 MB/s | 7,119 MB/s | 181x at 200 B |
| base65536 | decode | 0.020 μs | 0.063 μs | 4,482 MB/s | 4,471 MB/s | 162x at 200 B |
| base65536 (PyPI base65536 0.1.1) | encode | 0.199 μs | 7.525 μs | 27 MB/s | 27 MB/s | — |
| base65536 (PyPI base65536 0.1.1) | decode | 0.156 μs | 12.408 μs | 17 MB/s | 18 MB/s | — |
| braille | encode | 0.019 μs | 0.166 μs | 1,397 MB/s | 1,407 MB/s | 94x at 200 B |
| braille | decode | 0.016 μs | 0.268 μs | 796 MB/s | 801 MB/s | 69x at 200 B |
| hexagram | encode | 0.019 μs | 0.198 μs | 1,163 MB/s | 1,164 MB/s | 102x at 200 B |
| hexagram | decode | 0.017 μs | 0.319 μs | 672 MB/s | 651 MB/s | 72x at 200 B |
| uro14 | encode | 0.018 μs | 0.121 μs | 1,903 MB/s | 1,947 MB/s | 106x at 200 B |
| uro14 | decode | 0.016 μs | 0.198 μs | 1,028 MB/s | 1,029 MB/s | 93x at 200 B |
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
