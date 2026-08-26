"""Public face of the base32768 codec; the package ``__init__`` re-exports everything here."""

from __future__ import annotations

from radixly._codec import Codec
from radixly._codec import register
from radixly._core import base32768_decode
from radixly._core import base32768_encode

__all__ = ("BASE32768", "BITS_PER_CHAR", "decode", "encode", "encoded_len", "max_bytes")

encode = base32768_encode
decode = base32768_decode

BITS_PER_CHAR = 15


def encoded_len(num_bytes: int) -> int:
    """Exact length of ``encode(data)`` for a ``num_bytes``-byte payload, without encoding anything."""
    if num_bytes < 0:
        msg = f"num_bytes must be >= 0, got {num_bytes}"
        raise ValueError(msg)
    return (8 * num_bytes + 14) // BITS_PER_CHAR


def max_bytes(num_chars: int) -> int:
    """Largest payload that encodes into at most ``num_chars`` characters."""
    if num_chars < 0:
        msg = f"num_chars must be >= 0, got {num_chars}"
        raise ValueError(msg)
    return BITS_PER_CHAR * num_chars // 8


BASE32768 = Codec(
    name="base32768",
    bits_per_char=BITS_PER_CHAR,
    encode=base32768_encode,
    decode=base32768_decode,
    encoded_len=encoded_len,
    max_bytes=max_bytes,
)

register(BASE32768)
