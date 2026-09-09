# hexagram

6 bits per character: one I Ching hexagram (U+4DC0–U+4DFF) per six bits. A
preset of the contiguous-block factory.

## When to use it

The narrowest alphabet — 64 code points — at base64's density, when the
channel tolerates only a small, contiguous range.

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
.. autodata:: BITS_PER_CHAR
.. data:: HEXAGRAM
   :type: radixly.Codec

   The codec as a value, registered under ``"hexagram"``.
```
