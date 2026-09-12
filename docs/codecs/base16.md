# base16

4 bits per character: two uppercase hexadecimal digits per byte, RFC 4648
section 8.

The oldest binary-to-text encoding there is, in its strict form. Byte `0xAB`
becomes `AB`, nothing is padded, and `n` bytes become `2 * n` characters.
The output is what the standard library's `b16encode` produces; the decoder
is stricter than `b16decode`: lowercase digits, whitespace and an odd digit
count are errors, so one payload has exactly one accepted spelling.

## When to use it

100 characters hold 50 bytes, the fewest of any codec here. Its value is
not density but reach: hexadecimal is readable, greppable, and accepted by
every system that accepts text at all. Pick it for identifiers, checksums
and debugging output, or when the other side is a human.

It does not save bytes: as UTF-8 each character costs one, so the text is
twice the payload.

## Truncation behavior

A cut after an even number of characters decodes, without an error, to the
first half as many bytes; a cut after an odd number raises
{class}`~radixly.DecodeError` at the end of the text. There is no padding,
no length and no checksum, so half of all cuts pass, every one of them to a
prefix.

```python
from radixly import base16

payload = bytes(range(20))
text = base16.encode(payload)            # 40 characters
base16.decode(text[:8]) == payload[:4]   # True
```

If a shortened string must be caught, carry a length or checksum alongside
it, or use {doc}`uro14`, whose length prefix rejects every truncation below
its 16,384-byte window.

## Standard library

`radixly.compat.base64.b16encode` and `b16decode` are the standard library's
functions, the `casefold` option included, running on the same C. See
{doc}`../compat`.

## Benchmarks

The rows marked `stdlib` time the standard library's `b16encode` and
`b16decode`, with the encoder's `bytes` result decoded to `str` for a like
comparison.

```{include} ../benchmarks/base16.md
```

## Reference

```{eval-rst}
.. currentmodule:: radixly.base16

.. autofunction:: encode(data: collections.abc.Buffer, /) -> str
.. autofunction:: decode(data: str, /) -> bytes
.. autofunction:: encoded_len
.. autofunction:: max_bytes
.. data:: BITS_PER_CHAR
   :type: int
   :value: 4

   Payload bits per character: one hexadecimal digit.

.. data:: BASE16
   :type: radixly.Codec

   The codec as a value, registered under ``"base16"``.
```
