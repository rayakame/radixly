# Copyright (c) 2026-present rayakame
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
"""uro14: 14 bits per CJK character behind a length prefix.

Truncations under 16,384 bytes always fail, bigger payloads wrap the claim. b"" encodes to the lone prefix U+4E00.
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
    """Decode strictly.

    14-bit characters can leave up to 13 padding bits, so a body fits two payload lengths; the claim picks one.
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
