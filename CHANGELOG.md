# Changelog

<!-- towncrier release notes start -->

## 1.1.0 (2026-10-26)

### Breaking changes

- `Codec.bits_per_char` and every codec's `BITS_PER_CHAR` are floats, `6.4` for base85 and z85, so an `int` annotation or `isinstance` check no longer holds ([#43](https://github.com/rayakame/radixly/pull/43))

### Added

- base65536 codec: qntm's spec at 16 bits per character, in C ([#35](https://github.com/rayakame/radixly/pull/35))
- base2048 codec: qntm's spec at 11 bits per character, in C ([#35](https://github.com/rayakame/radixly/pull/35))
- `radixly.compat.base64`, the standard library drop-in: the `b16`, `b32` and `b32hex` encoders and decoders in C, passing CPython's own `test_base64` ([#37](https://github.com/rayakame/radixly/pull/37))
- base16, base32 and base32hex codecs: RFC 4648 in C, strict decoding ([#37](https://github.com/rayakame/radixly/pull/37))
- `radixly.compat.base64`: the `b64`, `standard_b64` and `urlsafe_b64` encoders and decoders in C, `altchars` and `validate` included, `b64decode` matching the running interpreter's `binascii.a2b_base64` ([#39](https://github.com/rayakame/radixly/pull/39))
- base64 and base64url codecs: RFC 4648 in C, strict decoding ([#39](https://github.com/rayakame/radixly/pull/39))
- `radixly.compat.base64`: the `a85`, `b85` and `z85` encoders and decoders in C, every option included, `z85` on 3.13 and later ([#42](https://github.com/rayakame/radixly/pull/42))
- base85 and z85 codecs: the RFC 1924 and ZeroMQ alphabets in C, strict decoding ([#43](https://github.com/rayakame/radixly/pull/43))
- `radixly.compat.base64` is complete: with `encode`, `decode`, `encodebytes` and `decodebytes`, every function of the standard library's `base64` runs in C and matches it down to error messages and exception chains ([#45](https://github.com/rayakame/radixly/pull/45))
- Wheels for CPython 3.15 ([#55](https://github.com/rayakame/radixly/pull/55))
- `radixly.compat.base64` follows the `base64` that CPython 3.15 rebuilt: the `padded`, `wrapcol`, `ignorechars`, `canonical` and `pad` keywords and the new errors and warnings, picked at import from the running interpreter ([#55](https://github.com/rayakame/radixly/pull/55))

### Fixed

- `DecodeError` keeps its notes and attributes through `pickle`, `copy.copy` and `copy.deepcopy` ([#37](https://github.com/rayakame/radixly/pull/37))
- On 3.11, importing `radixly._core` into a subinterpreter raises `ImportError`, as on 3.12 and later ([#37](https://github.com/rayakame/radixly/pull/37))
- `encoded_len` and `max_bytes` on every codec take integers only, through `operator.index`, so a float now raises `TypeError` ([#44](https://github.com/rayakame/radixly/pull/44))

### Documentation

- Link previews: Open Graph tags and a social card on every docs page ([#34](https://github.com/rayakame/radixly/pull/34))
- Benchmark record, charts and README table measured again after the engine rework ([#57](https://github.com/rayakame/radixly/pull/57))
- Every page rewritten to be short: one template per codec, diagrams drawn from the codecs at build time, and the drop-in's speed against the standard library from the benchmark record ([#59](https://github.com/rayakame/radixly/pull/59))

### Other

- GitHub releases attach the sdist only; the wheels are on PyPI ([#31](https://github.com/rayakame/radixly/pull/31))
- Benchmarks compare base65536 and base2048 with their PyPI namesakes; PyPI's base2048 uses another alphabet, so its rows compare speed only ([#35](https://github.com/rayakame/radixly/pull/35))
- Benchmarks compare the RFC 4648 codecs and the 85 pair with the standard library's `base64` ([#37](https://github.com/rayakame/radixly/pull/37), [#39](https://github.com/rayakame/radixly/pull/39), [#43](https://github.com/rayakame/radixly/pull/43))
- Benchmarks compare base64 and base64url with pybase64, a SIMD C extension ([#41](https://github.com/rayakame/radixly/pull/41))
- Tests catch memory that any C function fails to give back, on its error paths too ([#47](https://github.com/rayakame/radixly/pull/47))
- The RFC 4648 codecs, the 85 pair and the drop-in are faster: on 3.15 the drop-in's encoders run 1.5 to 2.2 times as fast as the standard library's and its 85 and base16 decoders 2.6 to 4 times, and on 3.14 and earlier `b64decode` runs 3.5 times as fast as before ([#56](https://github.com/rayakame/radixly/pull/56))


## 1.0.0 (2026-09-11)

### Added

- base32768 codec: qntm's spec at 15 bits per character, in C ([#6](https://github.com/rayakame/radixly/pull/6), [#8](https://github.com/rayakame/radixly/pull/8))
- Strict, canonical decoding for every codec: one payload, one spelling, and a final character carrying no payload bits is rejected ([#8](https://github.com/rayakame/radixly/pull/8), [#11](https://github.com/rayakame/radixly/pull/11))
- Public API: per-codec modules with `encode`, `decode`, `encoded_len` and `max_bytes`, a registry via `get_codec` and `CODECS`, and `DecodeError` carrying the failing position ([#10](https://github.com/rayakame/radixly/pull/10))
- uro14, braille and hexagram codecs at 14, 8 and 6 bits per character, uro14 with a length prefix that catches truncation below 16,384 bytes ([#11](https://github.com/rayakame/radixly/pull/11))
- Typed package: `py.typed` and stubs for the C module, checked complete by pyright's `--verifytypes` ([#16](https://github.com/rayakame/radixly/pull/16))
- Wheels for CPython 3.11 to 3.14: Linux (x86_64 and aarch64, glibc and musl), macOS (Intel and Apple silicon) and Windows ([#17](https://github.com/rayakame/radixly/pull/17))

### Documentation

- Documentation at https://radixly.rayakame.dev: a getting-started guide, a page per codec with its measured truncation behavior, and benchmark charts ([#20](https://github.com/rayakame/radixly/pull/20))

### Other

- Test suite runs under ASan and UBSan in CI, with fuzz tests against hostile input ([#9](https://github.com/rayakame/radixly/pull/9))
- Benchmark suite with a committed record, CI gating the C versus reference ratio ([#13](https://github.com/rayakame/radixly/pull/13))
- Release flow: fragments, prepare-release and release workflows ([#23](https://github.com/rayakame/radixly/pull/23))
