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
"""Shared rejection tables: both implementations pinned to the same kind and position."""

from __future__ import annotations

from tests.reference import base65536 as base65536_reference

__all__ = ("BAD_CASES", "HOSTILE_CASES", "NON_STR_INPUTS", "TAIL_CASES")

# qntm's bad vectors; the position is radixly's contract, pinned by the reference.
BAD_CASES: dict[str, int] = {
    "abc": 0,
    "endOfStreamBeginsStream": 0,
    "endOfStreamMidStream": 127,
    "endOfStreamMidStreamEarlier": 81,
    "eosThenJunk": 0,
    "junkOnEnd": 128,
    "lineBreak": 128,
    "rogueEndOfStreamChar": 0,
    "twoEndsOfStream": 128,
}

_VALID_4_CHARS = base65536_reference.encode(bytes(8))  # four full 16-bit characters

HOSTILE_CASES: dict[str, tuple[str, int]] = {
    "ascii": ("A", 0),
    "below-first-block": ("㏿", 0),
    "gap-between-blocks": ("䴀", 0),
    "high-surrogate": ("\ud800", 0),
    "low-surrogate": ("\udfff", 0),
    "unassigned-astral": ("\U0001f600", 0),
    "past-last-block": ("\U00028600", 0),
    "max-code-point": ("\U0010ffff", 0),
    "astral-mid-string": (_VALID_4_CHARS + "\U0001f600" + _VALID_4_CHARS, 4),
    "surrogate-mid-string": (_VALID_4_CHARS + "\udc00" + _VALID_4_CHARS, 4),
}

_TAIL = base65536_reference.LOOKUP_E[8][0x42]  # the one-byte block character for b"B"

TAIL_CASES: dict[str, tuple[str, int]] = {
    "tail-then-pair": (_TAIL + _VALID_4_CHARS, 0),
    "tail-mid-string": (_VALID_4_CHARS + _TAIL + _VALID_4_CHARS, 4),
    "two-tails": (_TAIL + _TAIL, 0),
}

NON_STR_INPUTS: tuple[object, ...] = (b"bytes", 42)
