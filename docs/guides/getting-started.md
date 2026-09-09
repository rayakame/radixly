# Getting started

## Install

```
pip install radixly
```

Wheels ship for CPython 3.11–3.14 on Linux (x86_64, aarch64, musl), macOS
(Intel, Apple silicon) and Windows (64-bit). radixly is a C extension with no
pure-Python fallback; anything else builds from the sdist and needs a C compiler.

## Encode and decode

```python
import radixly

text = radixly.uro14.encode(b"hello")
data = radixly.uro14.decode(text)
assert data == b"hello"
```

`encode` accepts any bytes-like object (`bytes`, `bytearray`, `memoryview`, …)
and returns a `str`; passing a `str` raises `TypeError`. `decode` is strict:
an invalid or misplaced character, broken padding or a non-canonical final
character raises {class}`radixly.DecodeError` carrying the offending position.

## Size arithmetic without encoding

```python
radixly.base32768.encoded_len(100)   # characters produced by 100 bytes
radixly.base32768.max_bytes(100)     # largest payload that fits 100 characters
```

:::{note}
This guide is a skeleton; the walkthrough is still being written.
:::
