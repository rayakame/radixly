# Getting started

## Install

```
pip install radixly
```

Releases ship wheels for CPython 3.11 to 3.14 on Linux (x86_64, aarch64,
musl), macOS (Intel and Apple silicon) and Windows (64-bit). radixly is a C
extension with no pure-Python fallback, so on any other platform, or when
installing a pre-release from source, pip builds the sdist and needs a C
compiler.

## A first round trip

Every codec lives in its own module and exposes the same two functions:

```python
import radixly

text = radixly.uro14.encode(b"hello")
data = radixly.uro14.decode(text)
assert data == b"hello"
```

`encode` takes any bytes-like object (`bytes`, `bytearray`, `memoryview`, an
array, a NumPy buffer) and returns a `str`. Passing a `str` raises
`TypeError`; encode your text first. `decode` takes a `str` and returns
`bytes`.

Decoding is strict. If the string is not something this codec could have
produced, you get a {class}`~radixly.DecodeError` that says why and where:

```python
try:
    radixly.base32768.decode("hello")
except radixly.DecodeError as error:
    print(error)           # invalid base32768 character U+68 at index 0
    print(error.position)  # 0
```

`DecodeError` is a `ValueError`, so an existing `except ValueError` keeps
working.

## Planning around a length limit

You rarely need to encode something to learn how long it would be. Every
codec has two helpers that do the arithmetic without touching the data:

```python
radixly.base32768.encoded_len(16)   # 9: characters produced by 16 bytes
radixly.base32768.max_bytes(100)    # 187: largest payload that fits 100 characters
```

`encoded_len` is exact, so it is safe to reserve space with. `max_bytes`
answers the question a length-limited field poses: how much can I put in
here?

## The registry

Each codec module also exposes its codec as a value, a
{class}`~radixly.Codec`, and registers it under its name. That lets you pick
a codec at runtime, by name or by property, instead of hard-coding an import:

```python
codec = radixly.get_codec("uro14")
codec.bits_per_char        # 14
codec.encode(b"hello")     # the same function as radixly.uro14.encode
codec.max_bytes(100)       # 173
```

{data}`radixly.CODECS` is a read-only mapping of every registered codec, in
registration order. Asking it which codec fits the most into a 100-character
field is one line:

```python
list(radixly.CODECS)                                   # ['base32768', 'braille', 'hexagram', 'uro14']
{name: c.max_bytes(100) for name, c in radixly.CODECS.items()}
# {'base32768': 187, 'braille': 100, 'hexagram': 75, 'uro14': 173}
```

A name that is not registered raises `KeyError` with the registered names in
the message. {func}`radixly.register` adds a codec of your own to the same
mapping, as long as the name is free.

A `Codec` is a frozen dataclass whose fields are the codec module's own
functions. Calling `codec.encode(data)` is one attribute load and the C call,
the same cost as calling the module function directly.
