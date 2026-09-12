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
"""base16, RFC 4648 section 8: two uppercase hexadecimal digits per byte, nothing else accepted."""

from __future__ import annotations

import typing

from tests.reference import errors

ALPHABET: typing.Final[str] = "0123456789ABCDEF"
BITS_PER_CHAR: typing.Final[int] = 4


def encode(data: bytes) -> str:
    """Encode bytes as uppercase hexadecimal."""
    return "".join(ALPHABET[byte >> 4] + ALPHABET[byte & 0xF] for byte in data)


def decode(string: str) -> bytes:
    """Decode strictly; an odd length raises at the end, after every character was checked."""
    values: list[int] = []
    for index, char in enumerate(string):
        value = ALPHABET.find(char)
        if value < 0:
            msg = f"invalid base16 character {char!r} (U+{ord(char):04X}) at index {index}"
            raise errors.DecodeError(index, message=msg)
        values.append(value)
    if len(values) % 2:
        msg = f"odd length: {len(string)} characters, the last byte needs two digits"
        raise errors.DecodeError(len(string), message=msg)
    return bytes((values[i] << 4) | values[i + 1] for i in range(0, len(values), 2))
