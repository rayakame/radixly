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

Releases ship wheels for CPython 3.11 to 3.15 on Linux, macOS and Windows.
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
| [z85](https://radixly.rayakame.dev/en/latest/codecs/z85.html) | 6.4 | 80 bytes | ZeroMQ: base85 with `.:/[]` in place of `` ` ``, `;`, `\|`, `_` and `~` | partly |
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

```python
from radixly.compat import base64
```

The standard library's `base64` with the same names, arguments, results and
errors, every one of its 22 functions in C, on CPython 3.11 through 3.15 with
the behavior of the interpreter it runs on. CPython's own `test_base64` passes
against it. What the swap buys, function by function, is on
[the drop-in page](https://radixly.rayakame.dev/en/latest/compat.html).

## Performance

Generated from the committed record run by the benchmark suite in
[`benchmarks/`](benchmarks/); no number here is typed by hand. Sizes below
64 KiB show per-call latency, larger ones sustained throughput; "vs reference"
is the speedup over the pure-Python oracle in `tests/reference/`.

<!-- radixly-bench:begin -->
*Measured on Intel(R) Core(TM) i9-14900KF (performance governor), CachyOS, kernel 7.3.0-4-cachyos, CPython 3.15.0, gcc 16.2.1 20260810, radixly 1.0.0 @ 1abf2e8, 2026-10-25T17:22:11+00:00.*

| codec | direction | 1 B | 200 B | 64 KiB | 1 MiB | vs reference |
|---|---|---|---|---|---|---|
| base16 | encode | 0.019 μs | 0.056 μs | 6,208 MB/s | 6,157 MB/s | 150x at 200 B |
| base16 | decode | 0.020 μs | 0.104 μs | 2,501 MB/s | 2,481 MB/s | 157x at 200 B |
| base16 (stdlib base64 3.15.0) | encode | 0.077 μs | 0.187 μs | 2,070 MB/s | 1,960 MB/s | — |
| base16 (stdlib base64 3.15.0) | decode | 0.192 μs | 0.529 μs | 642 MB/s | 448 MB/s | — |
| base32 | encode | 0.023 μs | 0.062 μs | 4,981 MB/s | 5,016 MB/s | 422x at 200 B |
| base32 | decode | 0.025 μs | 0.085 μs | 3,053 MB/s | 3,054 MB/s | 278x at 200 B |
| base32 (stdlib base64 3.15.0) | encode | 0.089 μs | 0.170 μs | 2,696 MB/s | 2,717 MB/s | — |
| base32 (stdlib base64 3.15.0) | decode | 0.112 μs | 0.200 μs | 2,394 MB/s | 2,255 MB/s | — |
| base32hex | encode | 0.023 μs | 0.062 μs | 5,008 MB/s | 5,013 MB/s | 418x at 200 B |
| base32hex | decode | 0.025 μs | 0.085 μs | 3,079 MB/s | 3,063 MB/s | 283x at 200 B |
| base32hex (stdlib base64 3.15.0) | encode | 0.099 μs | 0.179 μs | 2,710 MB/s | 2,733 MB/s | — |
| base32hex (stdlib base64 3.15.0) | decode | 0.121 μs | 0.213 μs | 2,383 MB/s | 2,255 MB/s | — |
| base64 | encode | 0.022 μs | 0.062 μs | 5,452 MB/s | 5,505 MB/s | 446x at 200 B |
| base64 | decode | 0.023 μs | 0.081 μs | 3,304 MB/s | 3,329 MB/s | 304x at 200 B |
| base64 (PyPI pybase64 1.5.1) | encode | 0.125 μs | 0.134 μs | 31,786 MB/s | 31,473 MB/s | — |
| base64 (PyPI pybase64 1.5.1) | decode | 0.144 μs | 0.185 μs | 23,681 MB/s | 25,543 MB/s | — |
| base64 (stdlib base64 3.15.0) | encode | 0.093 μs | 0.155 μs | 3,194 MB/s | 3,265 MB/s | — |
| base64 (stdlib base64 3.15.0) | decode | 0.128 μs | 0.211 μs | 2,922 MB/s | 2,800 MB/s | — |
| base64url | encode | 0.022 μs | 0.061 μs | 5,553 MB/s | 5,585 MB/s | 443x at 200 B |
| base64url | decode | 0.023 μs | 0.080 μs | 3,365 MB/s | 3,371 MB/s | 301x at 200 B |
| base64url (PyPI pybase64 1.5.1) | encode | 0.130 μs | 0.155 μs | 13,103 MB/s | 13,184 MB/s | — |
| base64url (PyPI pybase64 1.5.1) | decode | 0.154 μs | 0.217 μs | 9,444 MB/s | 9,721 MB/s | — |
| base64url (stdlib base64 3.15.0) | encode | 0.095 μs | 0.154 μs | 3,240 MB/s | 3,256 MB/s | — |
| base64url (stdlib base64 3.15.0) | decode | 0.138 μs | 0.269 μs | 1,868 MB/s | 1,802 MB/s | — |
| base85 | encode | 0.023 μs | 0.105 μs | 2,286 MB/s | 2,298 MB/s | 204x at 200 B |
| base85 | decode | 0.023 μs | 0.135 μs | 1,833 MB/s | 1,846 MB/s | 184x at 200 B |
| base85 (stdlib base64 3.15.0) | encode | 0.084 μs | 0.222 μs | 1,416 MB/s | 1,418 MB/s | — |
| base85 (stdlib base64 3.15.0) | decode | 0.048 μs | 0.256 μs | 1,004 MB/s | 991 MB/s | — |
| base2048 | encode | 0.020 μs | 0.128 μs | 1,751 MB/s | 1,784 MB/s | 109x at 200 B |
| base2048 | decode | 0.017 μs | 0.227 μs | 936 MB/s | 938 MB/s | 101x at 200 B |
| base2048 (PyPI base2048 0.1.3, other alphabet) | encode | 0.098 μs | 0.971 μs | 144 MB/s | 138 MB/s | — |
| base2048 (PyPI base2048 0.1.3, other alphabet) | decode | 0.096 μs | 0.822 μs | 132 MB/s | 122 MB/s | — |
| base32768 | encode | 0.020 μs | 0.113 μs | 2,001 MB/s | 2,004 MB/s | 104x at 200 B |
| base32768 | decode | 0.016 μs | 0.180 μs | 1,211 MB/s | 1,212 MB/s | 111x at 200 B |
| base65536 | encode | 0.020 μs | 0.045 μs | 7,148 MB/s | 7,143 MB/s | 174x at 200 B |
| base65536 | decode | 0.022 μs | 0.064 μs | 4,495 MB/s | 4,501 MB/s | 160x at 200 B |
| base65536 (PyPI base65536 0.1.1) | encode | 0.204 μs | 7.244 μs | 28 MB/s | 28 MB/s | — |
| base65536 (PyPI base65536 0.1.1) | decode | 0.156 μs | 13.124 μs | 16 MB/s | 16 MB/s | — |
| braille | encode | 0.020 μs | 0.166 μs | 1,410 MB/s | 1,416 MB/s | 89x at 200 B |
| braille | decode | 0.017 μs | 0.269 μs | 807 MB/s | 806 MB/s | 66x at 200 B |
| hexagram | encode | 0.020 μs | 0.199 μs | 1,174 MB/s | 1,171 MB/s | 97x at 200 B |
| hexagram | decode | 0.018 μs | 0.315 μs | 673 MB/s | 662 MB/s | 71x at 200 B |
| uro14 | encode | 0.020 μs | 0.122 μs | 1,923 MB/s | 1,963 MB/s | 100x at 200 B |
| uro14 | decode | 0.016 μs | 0.196 μs | 1,013 MB/s | 1,004 MB/s | 92x at 200 B |
| z85 | encode | 0.023 μs | 0.104 μs | 2,304 MB/s | 2,308 MB/s | 203x at 200 B |
| z85 | decode | 0.022 μs | 0.133 μs | 1,866 MB/s | 1,873 MB/s | 185x at 200 B |
| z85 (stdlib base64 3.15.0) | encode | 0.093 μs | 0.229 μs | 1,417 MB/s | 1,422 MB/s | — |
| z85 (stdlib base64 3.15.0) | decode | 0.055 μs | 0.266 μs | 1,009 MB/s | 1,010 MB/s | — |
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
