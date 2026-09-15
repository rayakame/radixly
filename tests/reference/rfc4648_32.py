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
"""Reference for the strict RFC 4648 base32 family: eight characters per five bytes, padding, zero pad bits."""

from __future__ import annotations

import typing

from tests.reference import errors
from tests.reference import shared

BITS_PER_CHAR: typing.Final[int] = 5
GROUP_BYTES: typing.Final[int] = 5
GROUP_CHARS: typing.Final[int] = 8
PAD: typing.Final[str] = "="

# Data characters a padded final group may hold, mapped to the payload bytes they carry.
PAYLOAD_BYTES: typing.Final[dict[int, int]] = {2: 1, 4: 2, 5: 3, 7: 4}


def encode(data: bytes, alphabet: str) -> str:
    """Encode bytes with ``alphabet``: full groups, then a zero-padded tail finished with ``=``."""
    out: list[str] = []
    for start in range(0, len(data), GROUP_BYTES):
        chunk = data[start : start + GROUP_BYTES]
        value = int.from_bytes(chunk.ljust(GROUP_BYTES, b"\0"), "big")
        chars = (shared.BITS_PER_BYTE * len(chunk) + BITS_PER_CHAR - 1) // BITS_PER_CHAR
        out.extend(alphabet[(value >> (40 - BITS_PER_CHAR * (k + 1))) & 0x1F] for k in range(chars))
        out.append(PAD * (GROUP_CHARS - chars))
    return "".join(out)


def _read_group(group: str, base: int, rev: dict[str, int], codec: str) -> tuple[int, int]:
    """Read one group: its 40-bit value and the count of data characters before its padding, 8 without."""
    acc = 0
    data_chars = GROUP_CHARS
    for k, char in enumerate(group):
        if char == PAD:
            data_chars = min(data_chars, k)
            continue
        value = rev.get(char)
        if value is None:
            msg = f"invalid {codec} character {char!r} (U+{ord(char):04X}) at index {base + k}"
            raise errors.DecodeError(base + k, message=msg)
        if data_chars != GROUP_CHARS:
            msg = f"data character {char!r} at index {base + k} after padding"
            raise errors.DecodeError(base + k, message=msg)
        acc = (acc << BITS_PER_CHAR) | value
    return acc, data_chars


def _finish_padded(acc: int, data_chars: int, pad_index: int, *, is_last: bool) -> bytes:
    """Return the payload of a padded group: last group only, one of four shapes, pad bits zero."""
    if not is_last:
        msg = f"padding at index {pad_index} before the end of the text"
        raise errors.DecodeError(pad_index, message=msg)
    payload = PAYLOAD_BYTES.get(data_chars)
    if payload is None:
        msg = f"{data_chars} data characters before the padding at index {pad_index}, not 2, 4, 5 or 7"
        raise errors.DecodeError(pad_index, message=msg)
    pad_bits = BITS_PER_CHAR * data_chars - shared.BITS_PER_BYTE * payload
    if acc & ((1 << pad_bits) - 1):
        msg = f"{pad_bits} padding bits not zero in the character at index {pad_index - 1}"
        raise errors.DecodeError(pad_index - 1, message=msg)
    return (acc >> pad_bits).to_bytes(payload, "big")


def _check_remainder(string: str, start: int, rev: dict[str, int], codec: str) -> None:
    """Check the characters after the last full group, so an invalid one reports its own index, then raise."""
    for i in range(start, len(string)):
        char = string[i]
        if char == PAD:
            msg = f"padding at index {i} in an incomplete group"
            raise errors.DecodeError(i, message=msg)
        if char not in rev:
            msg = f"invalid {codec} character {char!r} (U+{ord(char):04X}) at index {i}"
            raise errors.DecodeError(i, message=msg)
    msg = f"length {len(string)} is not a multiple of 8"
    raise errors.DecodeError(len(string), message=msg)


def decode(string: str, alphabet: str, codec: str) -> bytes:
    """Decode strictly; DecodeError with the index of the offending character, or the length when cut short."""
    rev = {char: value for value, char in enumerate(alphabet)}
    out = bytearray()
    num_groups, remainder = divmod(len(string), GROUP_CHARS)
    for g in range(num_groups):
        base = GROUP_CHARS * g
        acc, data_chars = _read_group(string[base : base + GROUP_CHARS], base, rev, codec)
        if data_chars == GROUP_CHARS:
            out += acc.to_bytes(GROUP_BYTES, "big")
            continue
        is_last = g == num_groups - 1 and not remainder
        out += _finish_padded(acc, data_chars, base + data_chars, is_last=is_last)
    if remainder:
        _check_remainder(string, GROUP_CHARS * num_groups, rev, codec)
    return bytes(out)
