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
"""Shared rejection tables for base16: same (input, position) on both sides."""

from __future__ import annotations

__all__ = ("INVALID_CASES", "NON_STR_INPUTS", "RFC_VECTORS")

# RFC 4648 section 10.
RFC_VECTORS: dict[bytes, str] = {
    b"": "",
    b"f": "66",
    b"fo": "666F",
    b"foo": "666F6F",
    b"foob": "666F6F62",
    b"fooba": "666F6F6261",
    b"foobar": "666F6F626172",
}

# Characters raise at their own index left to right; an odd length raises at the end, after every character.
INVALID_CASES: dict[str, tuple[str, int]] = {
    "lowercase": ("6a", 1),
    "non-hex-letter": ("6G", 1),
    "space": ("66 66", 2),
    "astral": ("\U0001f600", 0),
    "lone-surrogate": ("\ud800", 0),
    "nul": ("\x00", 0),
    "odd-length": ("686", 3),
    "odd-length-invalid-wins": ("6!6", 1),
    "invalid-mid-string": ("0000!!00", 4),
    "lowercase-last": ("00000a", 5),
}

NON_STR_INPUTS: tuple[object, ...] = (b"bytes", 42)
