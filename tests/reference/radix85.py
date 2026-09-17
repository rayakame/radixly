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
"""Base 85 with a four-byte word per five digits, shared by the base85 and z85 references: strict, one spelling."""

from __future__ import annotations

import typing

from tests.reference import errors

BASE: typing.Final[int] = 85
GROUP_BYTES: typing.Final[int] = 4
GROUP_CHARS: typing.Final[int] = 5
WORD_MAX: typing.Final[int] = 2**32 - 1
# 85 to the power of the digits a tail drops: the span of words that share the tail's digits.
DROPPED_SPAN: typing.Final[tuple[int, ...]] = (1, 85, 85**2, 85**3, 85**4)


def encode(data: bytes, alphabet: str) -> str:
    """Encode bytes with ``alphabet``: five digits per word, a tail keeps one digit more than its bytes."""
    out: list[str] = []
    for start in range(0, len(data), GROUP_BYTES):
        chunk = data[start : start + GROUP_BYTES]
        word = int.from_bytes(chunk.ljust(GROUP_BYTES, b"\0"), "big")
        digits = [alphabet[(word // BASE**k) % BASE] for k in reversed(range(GROUP_CHARS))]
        out.extend(digits[: len(chunk) + 1])
    return "".join(out)


def _read_group(group: str, start: int, rev: dict[str, int], codec: str) -> int:
    """Read one group of up to five characters as a word, the dropped digits as zero."""
    values: list[int] = []
    for k, char in enumerate(group):
        value = rev.get(char)
        if value is None:
            msg = f"invalid {codec} character {char!r} (U+{ord(char):04X}) at index {start + k}"
            raise errors.DecodeError(start + k, message=msg)
        values.append(value)
    values += [0] * (GROUP_CHARS - len(values))
    word = 0
    for value in values:
        word = word * BASE + value
    return word


def _finish_tail(word: int, count: int, last: int) -> bytes:
    """Return the tail's payload, the one word with zero low bytes among those sharing its digits."""
    payload = count - 1
    unit = 1 << (8 * (GROUP_BYTES - payload))
    rounded: int = -(-word // unit) * unit
    if rounded > min(WORD_MAX, word + DROPPED_SPAN[GROUP_CHARS - count] - 1):
        msg = f"the tail ending at index {last} is not the encoder's spelling"
        raise errors.DecodeError(last, message=msg)
    return rounded.to_bytes(GROUP_BYTES, "big")[:payload]


def decode(string: str, alphabet: str, codec: str) -> bytes:
    """Decode strictly; DecodeError with the index of the offending character, a group's at its last one."""
    rev = {char: value for value, char in enumerate(alphabet)}
    out = bytearray()
    for start in range(0, len(string), GROUP_CHARS):
        group = string[start : start + GROUP_CHARS]
        word = _read_group(group, start, rev, codec)
        last = start + len(group) - 1
        if len(group) == 1:
            msg = f"a tail of one character at index {last} carries no byte"
            raise errors.DecodeError(last, message=msg)
        if word > WORD_MAX:
            msg = f"the group ending at index {last} exceeds 32 bits"
            raise errors.DecodeError(last, message=msg)
        if len(group) == GROUP_CHARS:
            out += word.to_bytes(GROUP_BYTES, "big")
        else:
            out += _finish_tail(word, len(group), last)
    return bytes(out)
