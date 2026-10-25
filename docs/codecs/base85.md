# base85

Five characters per four bytes from the 85 characters of RFC 1924, the alphabet of the standard library's `b85encode` and of git's binary patches, decoded strictly.

::::{grid} 2 4 4 4
:gutter: 2

:::{grid-item-card} 6.4 bits
per character
:::
:::{grid-item-card} 4 → 5
bytes to characters, no padding
:::
:::{grid-item-card} 80 bytes
in 100 characters
:::
:::{grid-item-card} 3 cuts in 10
pass a truncation check
:::

::::

```{eval-rst}
.. raw:: html
   :file: ../_static/diagrams/base85-group.svg
```

```python
from radixly import base85

base85.encode(b"hi")          # 'XlV'
base85.decode("XlV")          # b'hi'
base85.encode(b"\x00" * 4)    # '00000'
base85.decode("X")            # DecodeError: a one-character tail
```

## Alphabet

`0` to `9`, `A` to `Z`, `a` to `z` and `` !#$%&()*+-;<=>?@^_`{|}~ ``. A group spells a 32-bit word in five digits; a one- to three-byte tail takes one character more than its bytes. A word above 32 bits, a one-character tail and a tail spelled any way but the encoder's are errors.

::::{grid} 1 2 2 2
:gutter: 2

:::{grid-item-card} Use it for
Channels that take all of printable ASCII and count every character: git chose it for binary diffs. A JSON string takes it unescaped, since no quote and no backslash is in the alphabet.
:::

:::{grid-item-card} Reach for another codec when
the text lands in a shell, a URL, HTML or Markdown, where `{}`, `|`, `` ` ``, `<>` and `&` are the format's: quote it, or use {doc}`z85` or {doc}`base64url`.
:::

::::

## Truncation

A cut inside a group of five raises {class}`~radixly.DecodeError` unless the tail happens to spell a shorter payload exactly; a cut on a group boundary decodes to a prefix. About three cuts in ten pass.

## Standard library

`radixly.compat.base64.b85encode` and `b85decode` run on this codec's C with the standard library's behavior, the `pad` flag and the lenient tail included. See {doc}`../compat`.

## Benchmarks

```{include} ../benchmarks/base85.md
```

The `stdlib base64` rows time `b85encode` and `b85decode`, pure Python before 3.15 and `binascii` from 3.15 on, the encoder's `bytes` result decoded to `str` for a like comparison.

## Reference

```{eval-rst}
.. currentmodule:: radixly.base85

.. autofunction:: encode(data: collections.abc.Buffer, /) -> str
.. autofunction:: decode(data: str, /) -> bytes
.. autofunction:: encoded_len
.. autofunction:: max_bytes
.. data:: BITS_PER_CHAR
   :type: float
   :value: 6.4

   Payload bits per character: five characters carry four bytes.

.. data:: BASE85
   :type: radixly.Codec

   The codec as a value, registered under ``"base85"``.
```
