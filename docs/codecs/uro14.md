# uro14

14 bits per character from one contiguous block of CJK ideographs, with a
length prefix. radixly's own design.

Every uro14 string starts with one character that states the payload length,
followed by the body at 14 payload bits per character. All characters come
from the 16,384 ideographs U+4E00 to U+8DFF, so `n` bytes become
`1 + ceil(8 * n / 14)` characters. The prefix claims `n` modulo 16,384; the
decoder uses it to check that the body is complete, and to settle which of
the two payload lengths a body can admit was meant. Decoding is strict: one
payload, one accepted spelling.

## When to use it

100 code points hold 173 bytes, close to base32768's 187, and unlike
base32768 a uro14 string can tell you when it has been cut short. Take it
when you would rather lose a few bytes of capacity than silently accept a
truncated payload.

The alphabet is a single block of CJK Unified Ideographs, every character
assigned and printable. That uniformity is also the trade: the text reads as
Chinese to a human eye and to any tool that guesses languages, and as UTF-8
each character costs three bytes.

## Truncation behavior

The length prefix is a checksum on length. When a string loses characters at
its end, the body no longer holds the number of bytes the prefix claims, and
{class}`~radixly.DecodeError` is raised at position 0. Below 16,384 bytes
this is absolute: every truncation of every payload is rejected, measured over
all cut positions.

```python
from radixly import uro14

payload = bytes(range(20))
text = uro14.encode(payload)   # 13 characters: the prefix, then 12
uro14.decode(text[:12])        # DecodeError: length prefix claims 20 bytes,
                               # impossible for 11 body characters
```

The claim wraps at 16,384 bytes, so the guarantee is windowed. For a bigger
payload a truncation is accepted only when the shortened body admits a length
that matches the claim modulo 16,384 and the padding happens to fit: on
random data that is about one cut position in sixty thousand. Payload sizes
are not capped; the window is the documented limit of the guarantee.

## Benchmarks

```{include} ../benchmarks/uro14.md
```

## The length window

The 14-bit length claim wraps at 16,384 bytes — see {doc}`../guides/uro14-window`.

## Reference

```{eval-rst}
.. currentmodule:: radixly.uro14

.. autofunction:: encode(data: collections.abc.Buffer, /) -> str
.. autofunction:: decode(data: str, /) -> bytes
.. autofunction:: encoded_len
.. autofunction:: max_bytes
.. data:: BITS_PER_CHAR
   :type: int
   :value: 14

   Payload bits carried by one body character; the length prefix is one character on top.

.. data:: URO14
   :type: radixly.Codec

   The codec as a value, registered under ``"uro14"``.
```
