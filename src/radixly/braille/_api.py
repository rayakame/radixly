"""Public face of the braille codec; the package ``__init__`` re-exports everything here."""

from __future__ import annotations

from radixly._codec import Codec
from radixly._codec import register
from radixly._core import braille_decode
from radixly._core import braille_encode

__all__ = ("BITS_PER_CHAR", "BRAILLE", "decode", "encode", "encoded_len", "max_bytes")

encode = braille_encode
decode = braille_decode

BITS_PER_CHAR = 8


def encoded_len(num_bytes: int) -> int:
    """Exact length of ``encode(data)``: one braille pattern per byte."""
    if num_bytes < 0:
        msg = f"num_bytes must be >= 0, got {num_bytes}"
        raise ValueError(msg)
    return num_bytes


def max_bytes(num_chars: int) -> int:
    """Largest payload that encodes into at most ``num_chars`` characters."""
    if num_chars < 0:
        msg = f"num_chars must be >= 0, got {num_chars}"
        raise ValueError(msg)
    return num_chars


BRAILLE = Codec(
    name="braille",
    bits_per_char=BITS_PER_CHAR,
    encode=braille_encode,
    decode=braille_decode,
    encoded_len=encoded_len,
    max_bytes=max_bytes,
)

register(BRAILLE)
