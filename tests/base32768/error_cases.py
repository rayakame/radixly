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

from tests.reference import base32768 as base32768_reference

__all__ = (
    "BAD_CASES",
    "CANONICALITY_CASES",
    "HOSTILE_NON_BMP",
    "NON_STR_INPUTS",
    "PICKLE_MESSAGE_CASES",
    "PICKLE_POSITION",
)

# Each bad vector pins both the failure mode and the position it occurs at.
BAD_CASES: dict[str, int] = {
    "bad-padding": 3,
    "bad0": 0,
    "not-base32768-char": 111,
}

_VALID_8_CHARS = base32768_reference.encode(bytes(15))  # 120 bits: 8 full 15-bit characters, no padding

# Astral hits the bounds guard, surrogates the painted cells; mid-string entries pin the index.
HOSTILE_NON_BMP: dict[str, tuple[str, int]] = {
    "astral": ("\U0001f600", 0),
    "high-surrogate": ("\ud800", 0),
    "low-surrogate": ("\udfff", 0),
    "astral-mid-string": (_VALID_8_CHARS + "\U0001f600" + _VALID_8_CHARS, 8),
    "surrogate-mid-string": (_VALID_8_CHARS + "\udc00" + _VALID_8_CHARS, 8),
}

_PURE_PADDING = base32768_reference.LOOKUP_E[7][127]  # 'ʟ', a 7-bit character that is all filler

# Deliberate divergence from qntm: zero-payload final chars are rejected so decode is injective.
CANONICALITY_CASES: dict[str, tuple[str, int]] = {
    "lone-padding": (_PURE_PADDING, 0),
    "appended-padding": (_VALID_8_CHARS + _PURE_PADDING, 8),
}

# For both implementations' type rejections: decode() takes str, full stop.
NON_STR_INPUTS: tuple[object, ...] = (b"bytes", 42)

# Pickle flavors: every view of the clone must agree on the message; "empty" checks option c composes.
PICKLE_POSITION: int = 5
PICKLE_MESSAGE_CASES: dict[str, tuple[dict[str, str], str]] = {
    "explicit": ({"message": "boom"}, "boom"),
    "empty": ({"message": ""}, ""),
    "generated": ({}, f"Decode Error at position {PICKLE_POSITION}"),
}
