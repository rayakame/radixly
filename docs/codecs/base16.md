# base16

Two uppercase hexadecimal digits per byte, RFC 4648 section 8: the plainest encoding, in its strict form.

::::{grid} 2 4 4 4
:gutter: 2

:::{grid-item-card} 4 bits
per character
:::
:::{grid-item-card} 1 → 2
byte to characters, nothing padded
:::
:::{grid-item-card} 50 bytes
in 100 characters
:::
:::{grid-item-card} 1 cut in 2
passes a truncation check
:::

::::

```{eval-rst}
.. raw:: html
   :file: ../_static/diagrams/base16-group.svg
```

```python
from radixly import base16

base16.encode(b"hi")      # '6869'
base16.decode("6869")     # b'hi'
base16.decode("686")      # DecodeError: odd length: 3 characters, ...
base16.decode("6a")       # DecodeError: invalid base16 character U+61
```

## Alphabet

`0` to `9` and `A` to `F`. Lowercase digits, whitespace and an odd digit count are errors; there is no `casefold`, so one payload has one spelling.

::::{grid} 1 2 2 2
:gutter: 2

:::{grid-item-card} Use it for
Identifiers, checksums, debugging output, anything a human reads: hexadecimal is greppable and every system that takes text takes it.
:::

:::{grid-item-card} Reach for another codec when
density matters ({doc}`base64` holds half again as much), or the string must announce a truncation ({doc}`uro14`).
:::

::::

## Truncation

A cut after an even number of characters decodes, without an error, to a prefix of the payload; a cut after an odd number raises {class}`~radixly.DecodeError` at the end of the text. Half of all cuts pass.

## Standard library

`radixly.compat.base64.b16encode` and `b16decode` run on this codec's C with the standard library's behavior, `casefold` included. See {doc}`../compat`.

## Benchmarks

```{include} ../benchmarks/base16.md
```

The `stdlib base64` rows time `b16encode` and `b16decode`, the encoder's `bytes` result decoded to `str` for a like comparison.

## Reference

```{eval-rst}
.. currentmodule:: radixly.base16

.. autofunction:: encode(data: collections.abc.Buffer, /) -> str
.. autofunction:: decode(data: str, /) -> bytes
.. autofunction:: encoded_len
.. autofunction:: max_bytes
.. data:: BITS_PER_CHAR
   :type: float
   :value: 4.0

   Payload bits per character: one hexadecimal digit.

.. data:: BASE16
   :type: radixly.Codec

   The codec as a value, registered under ``"base16"``.
```
