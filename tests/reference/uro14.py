"""uro14: 14 bits per character from the CJK block at U+4E00.

The first character carries the payload length mod 16384, so every tail
truncation of a valid string fails to decode. Front truncation is not
protected. The empty string is never valid; b"" encodes to the lone
length character U+4E00.
"""

from __future__ import annotations

import typing

from tests.reference import block
from tests.reference import errors
from tests.reference import shared

START: typing.Final[int] = 0x4E00
BITS_PER_CHAR: typing.Final[int] = 14

MODULUS: typing.Final[int] = 1 << BITS_PER_CHAR


def encode(data: bytes) -> str:
    """Encode bytes as uro14: length character first, then the body."""
    first = chr(START + len(data) % MODULUS)
    return first + block.encode(data, START, BITS_PER_CHAR)


def decode(string: str) -> bytes:
    """Decode strictly; DecodeError on invalid input or any length mismatch.

    A 14-bit single-width alphabet can leave up to 13 padding bits -- more
    than a byte -- so the bit stream alone cannot say where the payload ends.
    The claim resolves it: a body of k characters fits at most two payload
    lengths (ceil(8n/14) == k), and the claim picks one. That is the prefix's
    second job, after making every tail truncation detectable.
    """
    if not string:
        msg = "empty string: missing the length prefix"
        raise errors.DecodeError(0, message=msg)
    claim = ord(string[0]) - START
    if not (0 <= claim < MODULUS):
        msg = f"invalid character {string[0]!r} (U+{ord(string[0]):04X}) at index 0"
        raise errors.DecodeError(0, message=msg)
    body = string[1:]
    num_chars = len(body)
    upper = BITS_PER_CHAR * num_chars // shared.BITS_PER_BYTE
    payload_len = -1
    for n in (upper, upper - 1):
        fits = n >= 0 and (shared.BITS_PER_BYTE * n + BITS_PER_CHAR - 1) // BITS_PER_CHAR == num_chars
        if fits and n % MODULUS == claim:
            payload_len = n
            break
    if payload_len == -1:
        msg = f"length prefix claims {claim} bytes, impossible for {num_chars} body characters"
        raise errors.DecodeError(0, message=msg)

    acc = 0
    num_bits = 0
    out = bytearray()
    for index, char in enumerate(body):
        value = ord(char) - START
        if not (0 <= value < MODULUS):
            msg = f"invalid character {char!r} (U+{ord(char):04X}) at index {index + 1}"
            raise errors.DecodeError(index + 1, message=msg)
        acc = (acc << BITS_PER_CHAR) | value
        num_bits += BITS_PER_CHAR
        while num_bits >= shared.BITS_PER_BYTE and len(out) < payload_len:
            num_bits -= shared.BITS_PER_BYTE
            out.append(acc >> num_bits)
            acc &= (1 << num_bits) - 1

    # 0..13 bits remain; unmasked comparison so stray bits fail loudly.
    if acc != (1 << num_bits) - 1:
        last_index = len(string) - 1
        msg = f"expected {num_bits} padding bits set to 1 in final character at index {last_index}"
        raise errors.DecodeError(last_index, message=msg)
    return bytes(out)
