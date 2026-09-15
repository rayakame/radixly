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
| [base64url](https://radixly.rayakame.dev/en/latest/codecs/base64url.html) | 6 | 75 bytes | RFC 4648: base64 with `-` and `_` for `+` and `/` | partly |
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
*Measured on Intel(R) Core(TM) i9-14900KF (powersave governor), CachyOS, kernel 7.2.4-3-cachyos, CPython 3.14.6, gcc 16.2.1 20260810, radixly 1.0.0 @ ea46215, 2026-09-15T22:43:23+00:00.*

| codec | direction | 1 B | 200 B | 64 KiB | 1 MiB | vs reference |
|---|---|---|---|---|---|---|
| base16 | encode | 0.016 μs | 0.081 μs | 3,339 MB/s | 3,304 MB/s | 92x at 200 B |
| base16 | decode | 0.013 μs | 0.118 μs | 1,992 MB/s | 1,991 MB/s | 135x at 200 B |
| base16 (stdlib base64 3.14.6) | encode | 0.063 μs | 0.213 μs | 1,409 MB/s | 1,405 MB/s | — |
| base16 (stdlib base64 3.14.6) | decode | 0.101 μs | 0.352 μs | 829 MB/s | 614 MB/s | — |
| base32 | encode | 0.018 μs | 0.078 μs | 3,314 MB/s | 3,315 MB/s | 325x at 200 B |
| base32 | decode | 0.021 μs | 0.136 μs | 1,661 MB/s | 1,660 MB/s | 166x at 200 B |
| base32 (stdlib base64 3.14.6) | encode | 0.502 μs | 7.253 μs | 28 MB/s | 28 MB/s | — |
| base32 (stdlib base64 3.14.6) | decode | 0.518 μs | 10.389 μs | 19 MB/s | 20 MB/s | — |
| base32hex | encode | 0.018 μs | 0.078 μs | 3,317 MB/s | 3,316 MB/s | 324x at 200 B |
| base32hex | decode | 0.021 μs | 0.135 μs | 1,662 MB/s | 1,662 MB/s | 167x at 200 B |
| base32hex (stdlib base64 3.14.6) | encode | 0.501 μs | 7.248 μs | 28 MB/s | 28 MB/s | — |
| base32hex (stdlib base64 3.14.6) | decode | 0.520 μs | 10.433 μs | 20 MB/s | 20 MB/s | — |
| base64 | encode | 0.018 μs | 0.069 μs | 3,882 MB/s | 3,851 MB/s | 380x at 200 B |
| base64 | decode | 0.021 μs | 0.124 μs | 1,994 MB/s | 1,994 MB/s | 191x at 200 B |
| base64 (stdlib base64 3.14.6) | encode | 0.066 μs | 0.209 μs | 1,491 MB/s | 1,470 MB/s | — |
| base64 (stdlib base64 3.14.6) | decode | 0.067 μs | 0.236 μs | 1,254 MB/s | 1,228 MB/s | — |
| base64url | encode | 0.018 μs | 0.069 μs | 3,886 MB/s | 3,876 MB/s | 379x at 200 B |
| base64url | decode | 0.021 μs | 0.124 μs | 1,993 MB/s | 1,992 MB/s | 190x at 200 B |
| base64url (stdlib base64 3.14.6) | encode | 0.090 μs | 0.287 μs | 1,090 MB/s | 1,080 MB/s | — |
| base64url (stdlib base64 3.14.6) | decode | 0.129 μs | 0.352 μs | 959 MB/s | 941 MB/s | — |
| base2048 | encode | 0.017 μs | 0.117 μs | 1,852 MB/s | 1,854 MB/s | 111x at 200 B |
| base2048 | decode | 0.014 μs | 0.196 μs | 1,122 MB/s | 1,121 MB/s | 104x at 200 B |
| base2048 (PyPI base2048 0.1.3, other alphabet) | encode | 0.093 μs | 0.930 μs | 155 MB/s | 148 MB/s | — |
| base2048 (PyPI base2048 0.1.3, other alphabet) | decode | 0.089 μs | 0.785 μs | 141 MB/s | 131 MB/s | — |
| base32768 | encode | 0.017 μs | 0.105 μs | 2,146 MB/s | 2,147 MB/s | 105x at 200 B |
| base32768 | decode | 0.014 μs | 0.161 μs | 1,367 MB/s | 1,363 MB/s | 109x at 200 B |
| base65536 | encode | 0.017 μs | 0.042 μs | 7,568 MB/s | 7,586 MB/s | 181x at 200 B |
| base65536 | decode | 0.018 μs | 0.061 μs | 4,764 MB/s | 4,763 MB/s | 149x at 200 B |
| base65536 (PyPI base65536 0.1.1) | encode | 0.186 μs | 6.938 μs | 29 MB/s | 29 MB/s | — |
| base65536 (PyPI base65536 0.1.1) | decode | 0.144 μs | 10.646 μs | 19 MB/s | 19 MB/s | — |
| braille | encode | 0.017 μs | 0.157 μs | 1,496 MB/s | 1,494 MB/s | 90x at 200 B |
| braille | decode | 0.015 μs | 0.252 μs | 855 MB/s | 854 MB/s | 67x at 200 B |
| hexagram | encode | 0.018 μs | 0.187 μs | 1,238 MB/s | 1,237 MB/s | 99x at 200 B |
| hexagram | decode | 0.016 μs | 0.297 μs | 686 MB/s | 650 MB/s | 73x at 200 B |
| uro14 | encode | 0.017 μs | 0.110 μs | 2,171 MB/s | 2,178 MB/s | 107x at 200 B |
| uro14 | decode | 0.015 μs | 0.218 μs | 966 MB/s | 978 MB/s | 78x at 200 B |
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
