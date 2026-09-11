# Changelog

<!-- towncrier release notes start -->

## 1.0.0 (2026-09-11)

### Added

- base32768 codec: qntm's spec at 15 bits per character, encode and decode in C, byte-identical to the reference vectors. ([#6](https://github.com/rayakame/radixly/pull/6), [#8](https://github.com/rayakame/radixly/pull/8))
- Strict, canonical decoding for every codec: one payload, one accepted spelling. A final character that carries no payload bits is rejected. ([#8](https://github.com/rayakame/radixly/pull/8), [#11](https://github.com/rayakame/radixly/pull/11))
- Public API: per-codec modules with `encode`, `decode`, `encoded_len` and `max_bytes`, a codec registry via `get_codec` and `CODECS`, and `DecodeError` carrying the failing position. ([#10](https://github.com/rayakame/radixly/pull/10))
- uro14, braille and hexagram codecs on a shared block engine. uro14 packs 14 bits per character and carries a length prefix that catches truncation below 16,384 bytes. ([#11](https://github.com/rayakame/radixly/pull/11))
- Typed package: `py.typed` and stubs for the C module, verified with pyright's verifytypes. ([#16](https://github.com/rayakame/radixly/pull/16))
- Wheels for CPython 3.11 to 3.14 on Linux (x86_64 and aarch64, glibc and musl), macOS (Intel and Apple silicon) and Windows. ([#17](https://github.com/rayakame/radixly/pull/17))

### Documentation

- Documentation at https://radixly.rayakame.dev: a getting-started guide, a page per codec with its measured truncation behavior, and benchmark charts. ([#20](https://github.com/rayakame/radixly/pull/20))

### Other

- Test suite runs under ASan and UBSan in CI, with fuzz tests against hostile input. ([#9](https://github.com/rayakame/radixly/pull/9))
- Benchmark suite with a committed record and CI gates on the C versus reference ratio. ([#13](https://github.com/rayakame/radixly/pull/13))
- Release flow: fragments, prepare-release and release workflows. ([#23](https://github.com/rayakame/radixly/pull/23))
