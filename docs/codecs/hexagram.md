# hexagram

One I Ching hexagram per six bits: base64's density in a single block of 64 symbols.

::::{grid} 2 4 4 4
:gutter: 2

:::{grid-item-card} 6 bits
per character
:::
:::{grid-item-card} 3 → 4
bytes to characters
:::
:::{grid-item-card} 75 bytes
in 100 characters
:::
:::{grid-item-card} 1 cut in 3
passes a truncation check
:::

::::

```{eval-rst}
.. raw:: html
   :file: ../_static/diagrams/hexagram-group.svg
```

```python
from radixly import hexagram

hexagram.encode(b"hi")        # '䷚䷆䷧'
hexagram.decode("䷚䷆䷧")      # b'hi'
hexagram.encoded_len(20)      # 27
```

## Alphabet

The Yijing Hexagram Symbols block U+4DC0 to U+4DFF, 64 symbols that cannot be mistaken for punctuation, whitespace or a path separator. Leftover bits are padded with ones; a final character that would carry no payload bits is never produced and never accepted.

::::{grid} 1 2 2 2
:gutter: 2

:::{grid-item-card} Use it for
Channels that tolerate only a small, contiguous range of code points.
:::

:::{grid-item-card} Reach for another codec when
ASCII is fine: {doc}`base64` has the same density at a third of the UTF-8 cost.
:::

::::

## Truncation

No length and no checksum: after `k` characters the `6 * k mod 8` leftover bits must look like padding, always on every fourth cut, never when the last character would carry no payload. About one cut in three passes, to a prefix; the rest raise {class}`~radixly.DecodeError` at the last character.

## Benchmarks

```{include} ../benchmarks/hexagram.md
```

## Reference

```{eval-rst}
.. currentmodule:: radixly.hexagram

.. autofunction:: encode(data: collections.abc.Buffer, /) -> str
.. autofunction:: decode(data: str, /) -> bytes
.. autofunction:: encoded_len
.. autofunction:: max_bytes
.. data:: BITS_PER_CHAR
   :type: float
   :value: 6.0

   Payload bits per character: one hexagram per six bits.

.. data:: HEXAGRAM
   :type: radixly.Codec

   The codec as a value, registered under ``"hexagram"``.
```
