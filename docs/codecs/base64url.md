# base64url

RFC 4648 section 5, decoded strictly: base64 with `-` and `_` in place of `+` and `/`, for URLs and file names, padding kept.

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
   :file: ../_static/diagrams/base64url-group.svg
```

```python
from radixly import base64url

base64url.encode(b"\xfb\xff")   # '-_8='
base64url.decode("-_8=")          # b'\xfb\xff'

# A JWT segment drops its padding; put it back before decoding.
segment = "eyJhbGciOiJub25lIn0"
base64url.decode(segment + "=" * (-len(segment) % 4))   # b'{"alg":"none"}'
```

## Alphabet

`A` to `Z`, `a` to `z`, `0` to `9`, `-` and `_`, with `=` as padding. `+` and `/` are errors, and so is missing padding: the RFC lets a decoder skip it when the payload length is known, this codec does not, so put it back before `decode`.

::::{grid} 1 2 2 2
:gutter: 2

:::{grid-item-card} Use it for
Path segments, query values, cookies, file names, and the token formats built on them: every character but the padding is unreserved in a URL and legal in a file name on every file system.
:::

:::{grid-item-card} Reach for another codec when
the channel is not a URL or a file name: {doc}`base64` is what the other side expects.
:::

::::

## Truncation

As base64: a cut inside a group of four raises {class}`~radixly.DecodeError`, a cut on a group boundary, one in four, decodes to a prefix without complaint.

## Standard library

`radixly.compat.base64.urlsafe_b64encode` and `urlsafe_b64decode` run on this codec's C with the standard library's leniency: the decoder also takes `+` and `/` and discards characters outside the alphabet. See {doc}`../compat`.

## Benchmarks

```{include} ../benchmarks/base64url.md
```

The `stdlib base64` rows time `urlsafe_b64encode` and `urlsafe_b64decode`, `binascii` plus a translation pass; the `PyPI pybase64` rows a SIMD C extension with `altchars=b"-_"` and `validate=True`. Text out on every side.

## Reference

```{eval-rst}
.. currentmodule:: radixly.base64url

.. autofunction:: encode(data: collections.abc.Buffer, /) -> str
.. autofunction:: decode(data: str, /) -> bytes
.. autofunction:: encoded_len
.. autofunction:: max_bytes
.. data:: BITS_PER_CHAR
   :type: float
   :value: 6.0

   Payload bits per character; a final group is padded with ``=`` to four characters.

.. data:: BASE64URL
   :type: radixly.Codec

   The codec as a value, registered under ``"base64url"``.
```
