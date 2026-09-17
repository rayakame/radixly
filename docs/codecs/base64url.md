# base64url

6 bits per character: {doc}`base64` with `-` and `_` in place of `+` and
`/`, RFC 4648 section 5, decoded strictly, padding kept.

The text is the standard library's `urlsafe_b64encode` output, returned as
`str`: the same four characters per three bytes and the same `=` padding, so
`n` bytes become `4 * ceil(n / 3)` characters. The decoder rejects `+` and
`/` along with everything else outside the alphabet, and it requires the
padding. The RFC lets a decoder skip the padding when the payload length is
known; this codec does not, so that one payload has exactly one accepted
spelling.

## When to use it

100 characters hold 75 bytes, the same as base64. Every character but the
padding is unreserved in a URL and legal in a file name on every file
system, which is what the alphabet is for: path segments, query values,
cookies, file names, and the token formats built on them. Many of those
formats (JWT among them) drop the padding on the wire; put it back before
`decode`, which rejects a short group:

```python
from radixly import base64url

segment = "eyJhbGciOiJub25lIn0"                   # a JWT header, its one "=" dropped
base64url.decode(segment + "=" * (-len(segment) % 4))
# b'{"alg":"none"}'
```

If the channel is not a URL or a file name, {doc}`base64` is the one the
other side expects.

## Truncation behavior

The same as base64: a cut inside a group of four raises
{class}`~radixly.DecodeError`, a cut on a group boundary passes and decodes
to a prefix of the payload. One cut in four lands on a boundary; there is no
length and no checksum to catch it.

```python
from radixly import base64url

payload = bytes(range(20))
text = base64url.encode(payload)             # 28 characters
base64url.decode(text[:16]) == payload[:12]  # True
```

If a shortened string must be caught, carry a length or checksum alongside
it, or use {doc}`uro14`, whose length prefix rejects every truncation below
its 16,384-byte window.

## Standard library

`radixly.compat.base64.urlsafe_b64encode` and `urlsafe_b64decode` port the
standard library's functions onto this codec's C, with the standard
library's leniency: its decoder also takes `+` and `/`, and discards
characters outside the alphabet. See {doc}`../compat`.

## Benchmarks

The rows marked `stdlib base64` time the standard library's
`urlsafe_b64encode` and `urlsafe_b64decode`, `binascii` plus a translation
pass in Python, with the encoder's `bytes` result decoded to `str` for a
like comparison.

```{include} ../benchmarks/base64url.md
```

## Reference

```{eval-rst}
.. currentmodule:: radixly.base64url

.. autofunction:: encode(data: collections.abc.Buffer, /) -> str
.. autofunction:: decode(data: str, /) -> bytes
.. autofunction:: encoded_len
.. autofunction:: max_bytes
.. data:: BITS_PER_CHAR
   :type: int
   :value: 6

   Payload bits per character; a final group is padded with ``=`` to four characters.

.. data:: BASE64URL
   :type: radixly.Codec

   The codec as a value, registered under ``"base64url"``.
```
