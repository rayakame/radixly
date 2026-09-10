# hexagram

6 bits per character: one I Ching hexagram per six bits.

The Yijing Hexagram Symbols block U+4DC0 to U+4DFF holds exactly 64
characters, which is base64's alphabet size in a single contiguous run. `n`
bytes become `ceil(8 * n / 6)` characters; when the bits do not divide
evenly the last character is padded with ones, and a final character that
would carry no payload bits at all is never produced and never accepted. It
is the second preset of radixly's contiguous-block codec.

## When to use it

Its density is base64's: 100 code points hold 75 bytes. The difference is
the alphabet, 64 assigned symbols from one block with nothing that could be
mistaken for punctuation, whitespace or a path separator. It fits a channel
that tolerates only a small, contiguous range of code points, and it costs
three UTF-8 bytes per character where base64 costs one.

## Truncation behavior

hexagram carries no length and no checksum. Whether a shortened string
decodes depends on the cut: after `k` characters the string holds `6 * k`
bits, and the leftover `6 * k mod 8` bits have to look like padding.

- Remainder 0 (every fourth cut): always valid, decodes to a prefix of the
  payload.
- Remainder 2 or 4: valid only if those payload bits happen to be all ones,
  one in four and one in sixteen on random data.
- Remainder 6: the final character would carry no payload bits, which the
  canonical rule rejects. Never valid.

Measured over all cut positions on random data, about one in three truncated
strings decodes without an error; the rest raise
{class}`~radixly.DecodeError` at the last character.

```python
from radixly import hexagram

payload = bytes(range(20))
text = hexagram.encode(payload)              # 27 characters
hexagram.decode(text[:24]) == payload[:18]   # True: 144 bits, no padding to check
hexagram.decode(text[:25])                   # DecodeError: 6 padding bits, no payload
```

If you need to know whether a string arrived whole, carry a length or
checksum alongside it, or use {doc}`uro14`.

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
   :type: int
   :value: 6

   Payload bits per character: one hexagram per six bits.

.. data:: HEXAGRAM
   :type: radixly.Codec

   The codec as a value, registered under ``"hexagram"``.
```
