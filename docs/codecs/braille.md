# braille

Every byte becomes one Braille pattern: bytes as plain text, nothing more.

::::{grid} 2 4 4 4
:gutter: 2

:::{grid-item-card} 8 bits
per character
:::
:::{grid-item-card} 1 → 1
byte to character
:::
:::{grid-item-card} 100 bytes
in 100 characters
:::
:::{grid-item-card} every cut
passes a truncation check
:::

::::

```{eval-rst}
.. raw:: html
   :file: ../_static/diagrams/braille-group.svg
```

```python
from radixly import braille

braille.encode(b"hi")        # '⡨⡩'
braille.decode("⡨⡩")         # b'hi'
len(braille.encode(bytes(20)))   # 20
```

## Alphabet

The Braille Patterns block U+2800 to U+28FF, 256 printable, assigned characters, one for every byte value: byte `b` becomes `U+2800 + b`. Offsets carry over, so the eighth byte is the eighth character.

::::{grid} 1 2 2 2
:gutter: 2

:::{grid-item-card} Use it for
A payload that has to be a string and nothing else: no whitespace, no control characters, one block, and byte offsets you can read off the text.
:::

:::{grid-item-card} Reach for another codec when
capacity matters: one character per byte gains nothing, and as UTF-8 each pattern costs three bytes.
:::

::::

## Truncation

Every prefix is itself valid: a string cut after `k` characters decodes, without an error, to the first `k` bytes. There is no padding, no length and no checksum to object.

## Benchmarks

```{include} ../benchmarks/braille.md
```

## Reference

```{eval-rst}
.. currentmodule:: radixly.braille

.. autofunction:: encode(data: collections.abc.Buffer, /) -> str
.. autofunction:: decode(data: str, /) -> bytes
.. autofunction:: encoded_len
.. autofunction:: max_bytes
.. data:: BITS_PER_CHAR
   :type: float
   :value: 8.0

   Payload bits per character: one byte per braille pattern.

.. data:: BRAILLE
   :type: radixly.Codec

   The codec as a value, registered under ``"braille"``.
```
