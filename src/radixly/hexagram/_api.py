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
"""Public face of the hexagram codec; the package ``__init__`` re-exports everything here."""

from __future__ import annotations

from radixly._codec import Codec
from radixly._codec import register
from radixly._core import hexagram_decode
from radixly._core import hexagram_encode

__all__ = ("BITS_PER_CHAR", "HEXAGRAM", "decode", "encode", "encoded_len", "max_bytes")

encode = hexagram_encode
decode = hexagram_decode

BITS_PER_CHAR = 6
"""Payload bits per character: one hexagram per six bits."""


def encoded_len(num_bytes: int) -> int:
    """Exact length of ``encode(data)`` for a ``num_bytes``-byte payload.

    Parameters
    ----------
    num_bytes
        Payload size in bytes.

    Returns
    -------
    int
        ``ceil(8 * num_bytes / 6)``.

    Raises
    ------
    ValueError
        If ``num_bytes`` is negative.

    Examples
    --------
    >>> from radixly import hexagram
    >>> hexagram.encoded_len(10)
    14
    """
    if num_bytes < 0:
        msg = f"num_bytes must be >= 0, got {num_bytes}"
        raise ValueError(msg)
    return (8 * num_bytes + 5) // BITS_PER_CHAR


def max_bytes(num_chars: int) -> int:
    """Largest payload that encodes into at most ``num_chars`` characters.

    Parameters
    ----------
    num_chars
        The channel's limit, counted in code points.

    Returns
    -------
    int
        ``floor(6 * num_chars / 8)``.

    Raises
    ------
    ValueError
        If ``num_chars`` is negative.

    Examples
    --------
    >>> from radixly import hexagram
    >>> hexagram.max_bytes(100)
    75
    """
    if num_chars < 0:
        msg = f"num_chars must be >= 0, got {num_chars}"
        raise ValueError(msg)
    return BITS_PER_CHAR * num_chars // 8


HEXAGRAM = Codec(
    name="hexagram",
    bits_per_char=BITS_PER_CHAR,
    encode=hexagram_encode,
    decode=hexagram_decode,
    encoded_len=encoded_len,
    max_bytes=max_bytes,
)

register(HEXAGRAM)
