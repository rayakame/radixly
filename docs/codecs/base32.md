# base32

RFC 4648 section 6, decoded strictly: letters and digits only, the alphabet that survives case folding.

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
   :file: ../_static/diagrams/base32-group.svg
```

```python
from radixly import base32

base32.encode(b"hi")          # 'NBUQ===='
base32.decode("NBUQ====")     # b'hi'
base32.decode("nbuq====")     # DecodeError: lowercase is not base32
```

## Alphabet

`A` to `Z` and `2` to `7`, with `=` as padding. The digits `0`, `1`, `8` and `9` are left out because they look like `O`, `I` and `B`. Lowercase letters, characters outside the alphabet, misplaced padding and nonzero pad bits are errors. Text that comes back lowercased goes through `str.upper` first, or through the drop-in's `b32decode` with `casefold=True`.

::::{grid} 1 2 2 2
:gutter: 2

:::{grid-item-card} Use it for
Case-insensitive channels: file names on case-folding file systems, codes read out loud or typed from paper, DNS-adjacent formats (strip the padding for transport, restore it before `decode`).
:::

:::{grid-item-card} Reach for another codec when
the channel is case-sensitive ({doc}`base64` carries a quarter more), or the text must sort like its bytes ({doc}`base32hex`).
:::

::::

## Truncation

Whole groups of eight are required, so a cut inside a group raises {class}`~radixly.DecodeError`. A cut on a group boundary, one in eight, decodes to a prefix without complaint.

## Standard library

`radixly.compat.base64.b32encode` and `b32decode` run on this codec's C with the standard library's behavior, `casefold` and `map01` included. See {doc}`../compat`.

## Benchmarks

```{include} ../benchmarks/base32.md
```

The `stdlib base64` rows time `b32encode` and `b32decode`, pure Python before 3.15 and `binascii` from 3.15 on, the encoder's `bytes` result decoded to `str` for a like comparison.

## Reference

```{eval-rst}
.. currentmodule:: radixly.base32

.. autofunction:: encode(data: collections.abc.Buffer, /) -> str
.. autofunction:: decode(data: str, /) -> bytes
.. autofunction:: encoded_len
.. autofunction:: max_bytes
.. data:: BITS_PER_CHAR
   :type: float
   :value: 5.0

   Payload bits per character; a final group is padded with ``=`` to eight characters.

.. data:: BASE32
   :type: radixly.Codec

   The codec as a value, registered under ``"base32"``.
```
