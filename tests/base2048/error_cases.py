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

from tests.reference import base2048 as base2048_reference

__all__ = (
    "BAD_CASES",
    "CANONICALITY_CASES",
    "HOSTILE_CASES",
    "NARROW_PINS",
    "NON_STR_INPUTS",
    "PADDING_CASES",
    "SHORT_CASES",
)

# qntm's bad vectors; the position is radixly's contract, pinned by the reference.
BAD_CASES: dict[str, int] = {
    "case-early-padding": 4,
    "caseDemo": 10,
    "every-byte": 186,
    "hatetris-wr": 261,
    "hatetris-wr-rle": 222,
    "hatetris-wr-rle2": 185,
    "padding-mismatch": 11,
}

_VALID_8_CHARS = base2048_reference.encode(bytes(11))  # 88 bits: 8 full 11-bit characters, no padding

HOSTILE_CASES: dict[str, tuple[str, int]] = {
    "ascii-outside-alphabet": ("!", 0),
    "first-past-table": ("\u1056", 0),
    "twitter-line": ("ᄀ", 0),
    "bmp-ceiling": ("￿", 0),
    "astral": ("\U0001f600", 0),
    "high-surrogate": ("\ud800", 0),
    "low-surrogate": ("\udfff", 0),
    "astral-mid-string": (_VALID_8_CHARS + "\U0001f600" + _VALID_8_CHARS, 8),
    "surrogate-mid-string": (_VALID_8_CHARS + "\udc00" + _VALID_8_CHARS, 8),
    "past-table-mid-string": (_VALID_8_CHARS + "ᄀ" + _VALID_8_CHARS, 8),
}

_PURE_PADDING = base2048_reference.LOOKUP_E[3][7]  # '7', a 3-bit character that is all filler

CANONICALITY_CASES: dict[str, tuple[str, int]] = {
    "lone-padding": (_PURE_PADDING, 0),
    "appended-padding": (_VALID_8_CHARS + _PURE_PADDING, 8),
    # 33 bits then z=15 puts four one-bits before the short filler, so only the canonicality rule can reject it.
    "short-after-four-full": ("888" + base2048_reference.LOOKUP_E[11][0xF] + _PURE_PADDING, 4),
}

# Padding bits that are not all ones; "881" is three zero bytes, "880" has the short character's pad bit zeroed.
PADDING_CASES: dict[str, tuple[str, int]] = {
    "short-final-zero-pad": ("880", 2),
    "long-final-zero-pad": ("8", 0),
    "long-final-zero-pad-mid": (_VALID_8_CHARS + "8", 8),
}

# A 3-bit character anywhere but last.
SHORT_CASES: dict[str, tuple[str, int]] = {
    "short-first": ("7" + _VALID_8_CHARS, 0),
    "short-mid": (_VALID_8_CHARS + "3" + _VALID_8_CHARS, 8),
    "two-shorts": ("77", 0),
}

# Single bytes 0 to 6 pad to indexes below 63, inside the repertoire's Latin-1 run: the C must hand back a
# 1-byte-kind str for them, ASCII for the first six and Latin-1 for the seventh.
NARROW_PINS: dict[bytes, str] = {bytes([b]): letter for b, letter in enumerate("FNVdltÐ")}

NON_STR_INPUTS: tuple[object, ...] = (b"bytes", 42)
