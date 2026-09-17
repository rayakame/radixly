# base64

6 bits per character from the letters `A` to `Z` and `a` to `z`, the digits
`0` to `9`, `+` and `/`, RFC 4648 section 4, decoded strictly.

Three bytes become four characters. A shorter tail is padded with `=` to a
full group, so `n` bytes become `4 * ceil(n / 3)` characters and the text
length is always a multiple of four. The characters are the standard
library's `b64encode` output, returned as `str`. The decoder takes the strict
reading of the RFC: characters outside the alphabet (`-` and `_` included),
whitespace, padding in the wrong place or amount, and pad bits that are not
zero are all errors, so one payload has exactly one accepted spelling.

## When to use it

100 characters hold 75 bytes, the most of any ASCII codec here. base64 is
the encoding every channel already speaks: MIME, JSON, HTTP headers, data
URLs. Its two punctuation characters are the catch. `+` and `/` are
reserved in URLs and `/` separates path components, so URLs, file names and
tokens carried in them want {doc}`base64url` instead. The alphabet is
case-sensitive; a channel that folds case needs {doc}`base32`.

It does not save bytes: as UTF-8 each character costs one, so the text is
four characters for every three bytes, a third longer than the payload, plus
the padding that rounds a one- or two-byte tail up to a full group.

## Truncation behavior

The decoder requires whole groups of four, so a cut inside a group raises
{class}`~radixly.DecodeError`: at the end of the text when the cut falls in
data characters, at the first `=` when it falls in the padding. A cut on a
group boundary passes, without an error, and decodes to a prefix of the
payload. One cut in four lands on a boundary; there is no length and no
checksum to catch it.

```python
from radixly import base64

payload = bytes(range(20))
text = base64.encode(payload)             # 28 characters
base64.decode(text[:16]) == payload[:12]  # True
```

If a shortened string must be caught, carry a length or checksum alongside
it, or use {doc}`uro14`, whose length prefix rejects every truncation below
its 16,384-byte window.

## Standard library

`radixly.compat.base64.b64encode`, `b64decode`, `standard_b64encode` and
`standard_b64decode` port the standard library's functions, `altchars` and
`validate` included, onto this codec's C. See {doc}`../compat`.

## Benchmarks

The rows marked `stdlib base64` time the standard library's `b64encode` and
`b64decode`, which are C already (`binascii`) behind a Python wrapper, with
the encoder's `bytes` result decoded to `str` for a like comparison.

```{include} ../benchmarks/base64.md
```

## Reference

```{eval-rst}
.. currentmodule:: radixly.base64

.. autofunction:: encode(data: collections.abc.Buffer, /) -> str
.. autofunction:: decode(data: str, /) -> bytes
.. autofunction:: encoded_len
.. autofunction:: max_bytes
.. data:: BITS_PER_CHAR
   :type: int
   :value: 6

   Payload bits per character; a final group is padded with ``=`` to four characters.

.. data:: BASE64
   :type: radixly.Codec

   The codec as a value, registered under ``"base64"``.
```
