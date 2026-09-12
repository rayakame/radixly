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
"""base32hex, RFC 4648 section 7: the alphabet 0-9 then A-V, so unpadded text sorts in byte order."""

from __future__ import annotations

import typing

from tests.reference import rfc4648_32

ALPHABET: typing.Final[str] = "0123456789ABCDEFGHIJKLMNOPQRSTUV"
BITS_PER_CHAR: typing.Final[int] = rfc4648_32.BITS_PER_CHAR


def encode(data: bytes) -> str:
    """Encode bytes as base32hex."""
    return rfc4648_32.encode(data, ALPHABET)


def decode(string: str) -> bytes:
    """Decode base32hex strictly."""
    return rfc4648_32.decode(string, ALPHABET, "base32hex")
