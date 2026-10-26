# base32hex

RFC 4648 section 7, decoded strictly: base32 with the alphabet `0` to `9` then `A` to `V`, so the text sorts like the bytes.

::::{grid} 2 4 4 4
:gutter: 2

:::{grid-item-card} 5 bits
per character
:::
:::{grid-item-card} 5 → 8
bytes to characters, `=` padded
:::
:::{grid-item-card} 60 bytes
in 100 characters
:::
:::{grid-item-card} 1 cut in 8
passes a truncation check
:::

::::

```{eval-rst}
.. raw:: html
   :file: ../_static/diagrams/base32hex-group.svg
```

```python
from radixly import base32hex

base32hex.encode(b"hi")          # 'D1KG===='
base32hex.decode("D1KG====")     # b'hi'
base32hex.encode(b"\x00") < base32hex.encode(b"\x01")   # True
```

## Alphabet

`0` to `9` and `A` to `V`, with `=` as padding. Payloads of one length encode to strings that sort in byte order, as does unpadded text of any length; `=` sorts between `9` and `A`, so padded strings of different lengths do not. NSEC3 (RFC 5155) uses this alphabet unpadded.

::::{grid} 1 2 2 2
:gutter: 2

:::{grid-item-card} Use it for
Database indexes and sorted directory listings where encoded strings of one length must keep their payloads' order.
:::

:::{grid-item-card} Reach for another codec when
humans read the text: {doc}`base32` leaves out the digits that look like letters.
:::

::::

## Truncation

As base32: a cut inside a group of eight raises {class}`~radixly.DecodeError`, a cut on a group boundary decodes to a prefix without an error.

## Standard library

`radixly.compat.base64.b32hexencode` and `b32hexdecode` run on this codec's C with the standard library's behavior, `casefold` included. See {doc}`../compat`.

## Benchmarks

```{include} ../benchmarks/base32hex.md
```

The `stdlib base64` rows time `b32hexencode` and `b32hexdecode`, pure Python before 3.15 and `binascii` from 3.15 on, the encoder's `bytes` result decoded to `str` for a like comparison.

## Reference

```{eval-rst}
.. currentmodule:: radixly.base32hex

.. autofunction:: encode(data: collections.abc.Buffer, /) -> str
.. autofunction:: decode(data: str, /) -> bytes
.. autofunction:: encoded_len
.. autofunction:: max_bytes
.. data:: BITS_PER_CHAR
   :type: float
   :value: 5.0

   Payload bits per character; a final group is padded with ``=`` to eight characters.

.. data:: BASE32HEX
   :type: radixly.Codec

   The codec as a value, registered under ``"base32hex"``.
```
