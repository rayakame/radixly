"""Public face of the uro14 codec; the package ``__init__`` re-exports everything here."""

from __future__ import annotations

from radixly._codec import Codec
from radixly._codec import register
from radixly._core import uro14_decode
from radixly._core import uro14_encode

__all__ = ("BITS_PER_CHAR", "URO14", "decode", "encode", "encoded_len", "max_bytes")

encode = uro14_encode
decode = uro14_decode

BITS_PER_CHAR = 14


def encoded_len(num_bytes: int) -> int:
    """Exact length of ``encode(data)``: the length prefix plus the body."""
    if num_bytes < 0:
        msg = f"num_bytes must be >= 0, got {num_bytes}"
        raise ValueError(msg)
    return 1 + (8 * num_bytes + 13) // BITS_PER_CHAR


def max_bytes(num_chars: int) -> int:
    """Largest payload that encodes into at most ``num_chars`` characters.

    The prefix eats one character, so nothing whatsoever fits in zero -- the
    contract has no truthful integer answer there and refuses instead of
    lying (the sibling codecs' max_bytes(0) == 0 genuinely holds; only uro14
    has a nonempty empty).
    """
    if num_chars < 0:
        msg = f"num_chars must be >= 0, got {num_chars}"
        raise ValueError(msg)
    if num_chars == 0:
        msg = "no payload fits in 0 characters: the length prefix needs one"
        raise ValueError(msg)
    return BITS_PER_CHAR * (num_chars - 1) // 8


URO14 = Codec(
    name="uro14",
    bits_per_char=BITS_PER_CHAR,
    encode=uro14_encode,
    decode=uro14_decode,
    encoded_len=encoded_len,
    max_bytes=max_bytes,
)

register(URO14)
