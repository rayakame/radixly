"""Public face of the hexagram codec; the package ``__init__`` re-exports everything here."""

from __future__ import annotations

from radixly._codec import Codec
from radixly._codec import register
from radixly._core import hexagram_decode
from radixly._core import hexagram_encode

__all__ = ("BITS_PER_CHAR", "HEXAGRAM", "decode", "encode", "encoded_len", "max_bytes")

encode = hexagram_encode
decode = hexagram_decode

BITS_PER_CHAR = 6


def encoded_len(num_bytes: int) -> int:
    """Exact length of ``encode(data)`` for a ``num_bytes``-byte payload."""
    if num_bytes < 0:
        msg = f"num_bytes must be >= 0, got {num_bytes}"
        raise ValueError(msg)
    return (8 * num_bytes + 5) // BITS_PER_CHAR


def max_bytes(num_chars: int) -> int:
    """Largest payload that encodes into at most ``num_chars`` characters."""
    if num_chars < 0:
        msg = f"num_chars must be >= 0, got {num_chars}"
        raise ValueError(msg)
    return BITS_PER_CHAR * num_chars // 8


HEXAGRAM = Codec(
    name="hexagram",
    bits_per_char=BITS_PER_CHAR,
    encode=hexagram_encode,
    decode=hexagram_decode,
    encoded_len=encoded_len,
    max_bytes=max_bytes,
)

register(HEXAGRAM)
