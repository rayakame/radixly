# base85

6.4 bits per character: five characters per four bytes from the 85
characters of RFC 1924, the alphabet of the standard library's `b85encode`
and of git's binary patches, decoded strictly.

Four bytes become one 32-bit word, written as five base-85 digits from `0`
to `9`, `A` to `Z`, `a` to `z` and `!#$%&()*+-;<=>?@^_`{|}~`. A shorter tail
of one to three bytes becomes one character more than its bytes, so `n`
bytes become `5 * (n // 4)` characters plus `n % 4 + 1`, and the text is
never one character past a multiple of five. The characters are the standard
library's `b85encode` output, returned as `str`. The decoder takes the strict
reading: characters outside the alphabet, whitespace, a group worth more than
32 bits, a one-character tail, and a tail spelled any way but the encoder's
are all errors, so one payload has exactly one accepted spelling.

## When to use it

100 characters hold 80 bytes, the most of any ASCII codec here. base85 is
the choice when every character counts and the channel takes all of
printable ASCII: git chose it for binary diffs for that reason. The price is
the alphabet, which reaches into `{}`, `|`, `` ` ``, `<>` and `&`: text that
lands in a shell, a URL, a JSON string or HTML has to be quoted first. When
it cannot be, {doc}`z85` trades those characters away at the same density.

It does not save bytes: as UTF-8 each character costs one, so the text is
five characters for every four bytes, a quarter longer than the payload.

## Truncation behavior

The decoder reads groups of five, so a cut inside a group usually raises
{class}`~radixly.DecodeError` at the last character of the cut group: a
one-character tail never decodes, and a tail of two to four characters
decodes only when it happens to be the exact spelling of a shorter payload,
which the remaining digits allow about one time in twelve. A cut on a group
boundary passes, without an error, and decodes to a prefix of the payload.
Taken over every cut, about three in ten pass; there is no length and no
checksum to catch them.

```python
from radixly import base85

payload = bytes(range(20))
text = base85.encode(payload)             # 25 characters
base85.decode(text[:10]) == payload[:8]   # True
```

If a shortened string must be caught, carry a length or checksum alongside
it, or use {doc}`uro14`, whose length prefix rejects every truncation below
its 16,384-byte window.

## Standard library

`radixly.compat.base64.b85encode` and `b85decode` port the standard
library's functions, the `pad` flag and the lenient tail included, onto this
codec's C. See {doc}`../compat`.

## Benchmarks

The rows marked `stdlib base64` time the standard library's `b85encode` and
`b85decode`, pure Python, with the encoder's `bytes` result decoded to `str`
for a like comparison.

```{include} ../benchmarks/base85.md
```

## Reference

```{eval-rst}
.. currentmodule:: radixly.base85

.. autofunction:: encode(data: collections.abc.Buffer, /) -> str
.. autofunction:: decode(data: str, /) -> bytes
.. autofunction:: encoded_len
.. autofunction:: max_bytes
.. data:: BITS_PER_CHAR
   :type: float
   :value: 6.4

   Payload bits per character: five characters carry four bytes.

.. data:: BASE85
   :type: radixly.Codec

   The codec as a value, registered under ``"base85"``.
```
