# base32hex

base32 with the alphabet `0` to `9` then `A` to `V`, RFC 4648 section 7,
decoded strictly.

Same groups, same padding, same 5 bits per character as {doc}`base32`;
only the alphabet differs. Its digits come first, so encoded strings sort in
the same order as the bytes they encode, which is why DNSSEC uses it. The
price is that `0`, `1` and `8` are back in the alphabet. radixly's encoder
produces exactly what the standard library's `b32hexencode` does; the
decoder is strict in the same way as base32's.

## When to use it

100 characters hold 60 bytes. Pick it over base32 when sorted encoded
strings must sort like their payloads, in a database index or a sorted
directory listing. Pick base32 when humans read the text.

## Truncation behavior

As base32: a cut inside a group of eight raises
{class}`~radixly.DecodeError` at the end of the text, a cut on a group
boundary decodes to a prefix without an error.

## Standard library

`radixly.compat.base64.b32hexencode` and `b32hexdecode` are the standard
library's functions, `casefold` included, running on the same C. See
{doc}`../compat`.

## Benchmarks

```{include} ../benchmarks/base32hex.md
```

## Reference

```{eval-rst}
.. currentmodule:: radixly.base32hex

.. autofunction:: encode(data: collections.abc.Buffer, /) -> str
.. autofunction:: decode(data: str, /) -> bytes
.. autofunction:: encoded_len
.. autofunction:: max_bytes
.. data:: BITS_PER_CHAR
   :type: int
   :value: 5

   Payload bits per character; a final group is padded with ``=`` to eight characters.

.. data:: BASE32HEX
   :type: radixly.Codec

   The codec as a value, registered under ``"base32hex"``.
```
