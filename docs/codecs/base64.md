# base64

RFC 4648 section 4, decoded strictly: the encoding every channel speaks, with one accepted spelling per payload.

::::{grid} 2 4 4 4
:gutter: 2

:::{grid-item-card} 6 bits
per character
:::
:::{grid-item-card} 3 → 4
bytes to characters, `=` padded
:::
:::{grid-item-card} 75 bytes
in 100 characters
:::
:::{grid-item-card} 1 cut in 4
passes a truncation check
:::

::::

```{eval-rst}
.. raw:: html
   :file: ../_static/diagrams/base64-group.svg
```

```python
from radixly import base64

base64.encode(b"hi")        # 'aGk='
base64.decode("aGk=")       # b'hi'
base64.decode("aGk")        # DecodeError: length 3 is not a multiple of 4
base64.encoded_len(20)      # 28
```

## Alphabet

`A` to `Z`, `a` to `z`, `0` to `9`, `+` and `/`, with `=` as padding. Everything else is an error: `-` and `_`, whitespace, padding in the wrong place or amount, pad bits that are not zero.

::::{grid} 1 2 2 2
:gutter: 2

:::{grid-item-card} Use it for
MIME, JSON, HTTP headers, data URLs: anywhere base64 is already the format.
:::

:::{grid-item-card} Reach for another codec when
the text goes into a URL or file name ({doc}`base64url`), the channel folds case ({doc}`base32`), or it counts characters rather than bytes ({doc}`base32768`).
:::

::::

## Truncation

Whole groups of four are required, so a cut inside a group raises {class}`~radixly.DecodeError`. A cut on a group boundary, one in four, decodes to a prefix without complaint.

## Standard library

`radixly.compat.base64.b64encode`, `b64decode`, `standard_b64encode`, `standard_b64decode`, `encodebytes`, `decodebytes`, `encode` and `decode` run on this codec's C with the standard library's behavior, `altchars` and `validate` included. See {doc}`../compat`.

## Benchmarks

```{include} ../benchmarks/base64.md
```

The `stdlib base64` rows time `b64encode` and `b64decode`, `binascii` behind a Python wrapper; the `PyPI pybase64` rows a C extension over libbase64's SIMD kernels. Text out and strict decoding on every side.

## Reference

```{eval-rst}
.. currentmodule:: radixly.base64

.. autofunction:: encode(data: collections.abc.Buffer, /) -> str
.. autofunction:: decode(data: str, /) -> bytes
.. autofunction:: encoded_len
.. autofunction:: max_bytes
.. data:: BITS_PER_CHAR
   :type: float
   :value: 6.0

   Payload bits per character; a final group is padded with ``=`` to four characters.

.. data:: BASE64
   :type: radixly.Codec

   The codec as a value, registered under ``"base64"``.
```
