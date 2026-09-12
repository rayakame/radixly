# base32

5 bits per character from the letters `A` to `Z` and the digits `2` to `7`,
RFC 4648 section 6, decoded strictly.

Five bytes become eight characters. A shorter tail is padded with `=` to a
full group, so `n` bytes become `8 * ceil(n / 5)` characters and the text
length is always a multiple of eight. The alphabet leaves out the digits
`0`, `1`, `8` and `9`; the first three are easily mistaken for `O`, `I` and
`B`. The characters are the standard library's `b32encode` output, returned
as `str`. The decoder takes the strict reading of the RFC: characters outside the alphabet,
lowercase letters, padding in the wrong place or amount, and pad bits that
are not zero are all errors, so one payload has exactly one accepted
spelling.

## When to use it

100 characters hold 60 bytes. base32 is the codec for channels that are
case-insensitive or hostile to punctuation: DNS labels, file names on
case-folding file systems, codes read out loud or typed from paper. The
alphabet is plain ASCII letters and digits, nothing else. Text that comes
back lowercased has to be uppercased before `decode`, or go through
`radixly.compat.base64.b32decode` with `casefold=True`.

It does not save bytes: as UTF-8 each character costs one, so the text is
1.6 times the payload. If the channel is case-sensitive, base64 carries
more.

## Truncation behavior

The decoder requires whole groups of eight, so a cut inside a group raises
{class}`~radixly.DecodeError`: at the end of the text when the cut falls in
data characters, at the first `=` when it falls in the padding. A cut on a
group boundary passes, without an error, and decodes to a prefix of the
payload.
One cut in eight lands on a boundary; there is no length and no checksum
to catch it.

```python
from radixly import base32

payload = bytes(range(20))
text = base32.encode(payload)            # 32 characters
base32.decode(text[:16]) == payload[:10]  # True
```

If a shortened string must be caught, carry a length or checksum alongside
it, or use {doc}`uro14`, whose length prefix rejects every truncation below
its 16,384-byte window.

## Standard library

`radixly.compat.base64.b32encode` and `b32decode` port the standard
library's functions, `casefold` and `map01` included, onto this codec's C.
See {doc}`../compat`.

## Benchmarks

The rows marked `stdlib base64` time the standard library's `b32encode` and
`b32decode`, pure Python, with the encoder's `bytes` result decoded to
`str` for a like comparison.

```{include} ../benchmarks/base32.md
```

## Reference

```{eval-rst}
.. currentmodule:: radixly.base32

.. autofunction:: encode(data: collections.abc.Buffer, /) -> str
.. autofunction:: decode(data: str, /) -> bytes
.. autofunction:: encoded_len
.. autofunction:: max_bytes
.. data:: BITS_PER_CHAR
   :type: int
   :value: 5

   Payload bits per character; a final group is padded with ``=`` to eight characters.

.. data:: BASE32
   :type: radixly.Codec

   The codec as a value, registered under ``"base32"``.
```
