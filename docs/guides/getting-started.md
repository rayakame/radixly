# Getting started

```bash
pip install radixly
```

Wheels cover CPython 3.11 to 3.15 on Linux (x86_64, aarch64, musl), macOS
(Intel and Apple silicon) and Windows (64-bit). There is no pure-Python
fallback: anywhere else pip builds from source and needs a C compiler.

## Encode and decode

```python
import radixly

text = radixly.uro14.encode(b"hello")   # str
radixly.uro14.decode(text)              # b'hello'
```

`encode` takes any bytes-like object and returns a `str`; a `str` argument
raises `TypeError`, so encode text first. `decode` takes a `str` and returns
`bytes`.

## Errors

Decoding is strict. A string the codec could not have produced raises
{class}`~radixly.DecodeError`, which says why and where:

```python
try:
    radixly.base32768.decode("hello")
except radixly.DecodeError as error:
    print(error)            # invalid base32768 character U+68 at index 0
    print(error.position)   # 0
```

`DecodeError` is a `ValueError`, so an existing `except ValueError` keeps
working.

## Size a field

Two helpers do the arithmetic without touching any data:

```python
radixly.base32768.encoded_len(16)   # 9: characters for 16 bytes, exact
radixly.base32768.max_bytes(100)    # 187: the most 100 characters hold
```

## Pick a codec at runtime

Every codec is also a {class}`~radixly.Codec` value in a registry, so a name
from a config file is enough:

```python
codec = radixly.get_codec("uro14")
codec.encode(b"hello")      # the same function as radixly.uro14.encode
codec.bits_per_char         # 14.0

{name: c.max_bytes(100) for name, c in radixly.CODECS.items()}
# {'base16': 50, 'base32': 60, ..., 'uro14': 173, 'z85': 80}
```

An unknown name raises `KeyError` listing the registered ones, and
{func}`radixly.register` adds a codec of your own. Calling through a `Codec`
costs the same as calling the module function.
