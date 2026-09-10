# braille

8 bits per character: every byte becomes one Braille pattern.

The Braille Patterns block U+2800 to U+28FF holds exactly 256 characters, one
for every byte value, so byte `b` becomes the character `U+2800 + b` and
nothing else happens: no bit shifting, no padding, no final short character.
The output is exactly as long as the input. It is one of two presets of
radixly's contiguous-block codec, which maps a fixed number of bits onto a
run of consecutive code points.

## When to use it

One character per byte gains you nothing over raw bytes in capacity. What it
gives you is a payload that is plain text: 256 printable, assigned characters
from a single block, with no whitespace or control characters among them,
that can travel through anything which accepts a string. Byte-to-character
alignment also means offsets carry over, so the eighth byte is the eighth
character. As UTF-8 each pattern costs three bytes.

## Truncation behavior

Every prefix of a braille string is itself a valid braille string. Cut one
anywhere and it decodes, without an error, to the first `k` bytes of the
payload. There is no padding, no length and no checksum, so the decoder has
nothing to object to.

```python
from radixly import braille

payload = bytes(range(20))
text = braille.encode(payload)         # 20 characters
braille.decode(text[:8]) == payload[:8]  # True, always
```

If a shortened string must be caught, carry a length or checksum alongside
it, or use {doc}`uro14`.

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
   :type: int
   :value: 8

   Payload bits per character: one byte per braille pattern.

.. data:: BRAILLE
   :type: radixly.Codec

   The codec as a value, registered under ``"braille"``.
```
