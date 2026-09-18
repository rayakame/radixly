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
| [base85](https://radixly.rayakame.dev/en/latest/codecs/base85.html) | 6.4 | 80 bytes | RFC 1924: letters, digits and 23 punctuation marks, the standard library's `b85` | partly |
| [z85](https://radixly.rayakame.dev/en/latest/codecs/z85.html) | 6.4 | 80 bytes | ZeroMQ: base85 without quotes, backslash or backquote | partly |
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
arguments, results and errors; every encoder and decoder (`b16`, `b32`,
`b32hex`, `b64`, `a85`, `b85` and, on 3.13 and later, `z85`) runs in C; the
four legacy functions (`encode` and `decode` on file objects, `encodebytes` and
`decodebytes` on bytes) are the standard library's own until ported.
CPython's own `test_base64` suite runs against it. See [the drop-in page](https://radixly.rayakame.dev/en/latest/compat.html).

## Performance

Generated from the committed record run by the benchmark suite in
[`benchmarks/`](benchmarks/); no number here is typed by hand. Sizes below
64 KiB show per-call latency, larger ones sustained throughput; "vs reference"
is the speedup over the pure-Python oracle in `tests/reference/`.

<!-- radixly-bench:begin -->
*Measured on Intel(R) Core(TM) i9-14900KF (performance governor), CachyOS, kernel 7.2.4-3-cachyos, CPython 3.14.6, gcc 16.2.1 20260810, radixly 1.0.0 @ d9cc547, 2026-09-17T20:52:16+00:00.*

| codec | direction | 1 B | 200 B | 64 KiB | 1 MiB | vs reference |
|---|---|---|---|---|---|---|
| base16 | encode | 0.016 μs | 0.081 μs | 3,306 MB/s | 3,324 MB/s | 92x at 200 B |
| base16 | decode | 0.013 μs | 0.118 μs | 1,990 MB/s | 1,992 MB/s | 134x at 200 B |
| base16 (stdlib base64 3.14.6) | encode | 0.062 μs | 0.212 μs | 1,356 MB/s | 1,393 MB/s | — |
| base16 (stdlib base64 3.14.6) | decode | 0.099 μs | 0.350 μs | 833 MB/s | 616 MB/s | — |
| base32 | encode | 0.018 μs | 0.076 μs | 3,321 MB/s | 3,319 MB/s | 330x at 200 B |
| base32 | decode | 0.021 μs | 0.139 μs | 1,663 MB/s | 1,660 MB/s | 159x at 200 B |
| base32 (stdlib base64 3.14.6) | encode | 0.502 μs | 7.284 μs | 28 MB/s | 28 MB/s | — |
| base32 (stdlib base64 3.14.6) | decode | 0.518 μs | 10.253 μs | 20 MB/s | 21 MB/s | — |
| base32hex | encode | 0.018 μs | 0.076 μs | 3,321 MB/s | 3,301 MB/s | 331x at 200 B |
| base32hex | decode | 0.021 μs | 0.139 μs | 1,662 MB/s | 1,661 MB/s | 163x at 200 B |
| base32hex (stdlib base64 3.14.6) | encode | 0.506 μs | 7.278 μs | 28 MB/s | 28 MB/s | — |
| base32hex (stdlib base64 3.14.6) | decode | 0.521 μs | 10.202 μs | 20 MB/s | 20 MB/s | — |
| base64 | encode | 0.018 μs | 0.075 μs | 3,791 MB/s | 3,722 MB/s | 346x at 200 B |
| base64 | decode | 0.020 μs | 0.123 μs | 1,994 MB/s | 1,991 MB/s | 190x at 200 B |
| base64 (PyPI pybase64 1.5.0) | encode | 0.116 μs | 0.122 μs | 34,407 MB/s | 33,163 MB/s | — |
| base64 (PyPI pybase64 1.5.0) | decode | 0.144 μs | 0.169 μs | 25,357 MB/s | 27,236 MB/s | — |
| base64 (stdlib base64 3.14.6) | encode | 0.066 μs | 0.209 μs | 1,497 MB/s | 1,480 MB/s | — |
| base64 (stdlib base64 3.14.6) | decode | 0.067 μs | 0.236 μs | 1,253 MB/s | 1,228 MB/s | — |
| base64url | encode | 0.018 μs | 0.074 μs | 3,781 MB/s | 3,705 MB/s | 346x at 200 B |
| base64url | decode | 0.020 μs | 0.123 μs | 1,994 MB/s | 1,994 MB/s | 191x at 200 B |
| base64url (PyPI pybase64 1.5.0) | encode | 0.124 μs | 0.144 μs | 13,894 MB/s | 14,098 MB/s | — |
| base64url (PyPI pybase64 1.5.0) | decode | 0.155 μs | 0.197 μs | 10,067 MB/s | 10,343 MB/s | — |
| base64url (stdlib base64 3.14.6) | encode | 0.089 μs | 0.293 μs | 1,093 MB/s | 1,082 MB/s | — |
| base64url (stdlib base64 3.14.6) | decode | 0.128 μs | 0.353 μs | 959 MB/s | 940 MB/s | — |
| base85 | encode | 0.019 μs | 0.092 μs | 2,759 MB/s | 2,747 MB/s | 221x at 200 B |
| base85 | decode | 0.015 μs | 0.121 μs | 1,993 MB/s | 1,990 MB/s | 195x at 200 B |
| base85 (stdlib base64 3.14.6) | encode | 0.456 μs | 5.103 μs | 42 MB/s | 34 MB/s | — |
| base85 (stdlib base64 3.14.6) | decode | 0.390 μs | 7.370 μs | 28 MB/s | 25 MB/s | — |
| base2048 | encode | 0.017 μs | 0.119 μs | 1,882 MB/s | 1,912 MB/s | 109x at 200 B |
| base2048 | decode | 0.013 μs | 0.213 μs | 997 MB/s | 998 MB/s | 96x at 200 B |
| base2048 (PyPI base2048 0.1.3, other alphabet) | encode | 0.093 μs | 0.930 μs | 152 MB/s | 145 MB/s | — |
| base2048 (PyPI base2048 0.1.3, other alphabet) | decode | 0.089 μs | 0.786 μs | 138 MB/s | 131 MB/s | — |
| base32768 | encode | 0.017 μs | 0.105 μs | 2,146 MB/s | 2,147 MB/s | 106x at 200 B |
| base32768 | decode | 0.013 μs | 0.170 μs | 1,280 MB/s | 1,280 MB/s | 104x at 200 B |
| base65536 | encode | 0.018 μs | 0.042 μs | 7,570 MB/s | 7,591 MB/s | 177x at 200 B |
| base65536 | decode | 0.018 μs | 0.059 μs | 4,766 MB/s | 4,769 MB/s | 154x at 200 B |
| base65536 (PyPI base65536 0.1.1) | encode | 0.188 μs | 6.974 μs | 29 MB/s | 29 MB/s | — |
| base65536 (PyPI base65536 0.1.1) | decode | 0.144 μs | 10.843 μs | 19 MB/s | 19 MB/s | — |
| braille | encode | 0.018 μs | 0.156 μs | 1,496 MB/s | 1,493 MB/s | 92x at 200 B |
| braille | decode | 0.015 μs | 0.252 μs | 855 MB/s | 854 MB/s | 67x at 200 B |
| hexagram | encode | 0.018 μs | 0.186 μs | 1,238 MB/s | 1,236 MB/s | 101x at 200 B |
| hexagram | decode | 0.015 μs | 0.297 μs | 717 MB/s | 717 MB/s | 72x at 200 B |
| uro14 | encode | 0.017 μs | 0.113 μs | 2,033 MB/s | 2,089 MB/s | 105x at 200 B |
| uro14 | decode | 0.014 μs | 0.177 μs | 1,098 MB/s | 1,210 MB/s | 96x at 200 B |
| z85 | encode | 0.018 μs | 0.088 μs | 2,756 MB/s | 2,746 MB/s | 234x at 200 B |
| z85 | decode | 0.015 μs | 0.121 μs | 1,992 MB/s | 1,990 MB/s | 195x at 200 B |
| z85 (stdlib base64 3.14.6) | encode | 0.473 μs | 5.175 μs | 41 MB/s | 34 MB/s | — |
| z85 (stdlib base64 3.14.6) | decode | 0.457 μs | 7.456 μs | 28 MB/s | 26 MB/s | — |
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
