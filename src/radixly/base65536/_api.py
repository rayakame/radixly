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
"""Public face of the base65536 codec; the package ``__init__`` re-exports everything here."""

from __future__ import annotations

from radixly._codec import Codec
from radixly._codec import register
from radixly._core import base65536_decode
from radixly._core import base65536_encode

__all__ = ("BASE65536", "BITS_PER_CHAR", "decode", "encode", "encoded_len", "max_bytes")

encode = base65536_encode
decode = base65536_decode

BITS_PER_CHAR = 16
"""Payload bits carried by one full character: two bytes; a final odd byte gets a character of its own."""


def encoded_len(num_bytes: int) -> int:
    """Exact length of ``encode(data)`` for ``num_bytes`` bytes, without encoding.

    Parameters
    ----------
    num_bytes
        Payload size in bytes.

    Returns
    -------
    int
        ``ceil(num_bytes / 2)``.

    Raises
    ------
    ValueError
        If ``num_bytes`` is negative.

    Examples
    --------
    >>> from radixly import base65536
    >>> base65536.encoded_len(11)
    6
    """
    if num_bytes < 0:
        msg = f"num_bytes must be >= 0, got {num_bytes}"
        raise ValueError(msg)
    return (num_bytes + 1) // 2


def max_bytes(num_chars: int) -> int:
    """Largest payload that fits in ``num_chars`` characters.

    Parameters
    ----------
    num_chars
        The limit, in code points.

    Returns
    -------
    int
        ``2 * num_chars``.

    Raises
    ------
    ValueError
        If ``num_chars`` is negative.

    Examples
    --------
    >>> from radixly import base65536
    >>> base65536.max_bytes(100)
    200
    """
    if num_chars < 0:
        msg = f"num_chars must be >= 0, got {num_chars}"
        raise ValueError(msg)
    return 2 * num_chars


BASE65536 = Codec(
    name="base65536",
    bits_per_char=BITS_PER_CHAR,
    encode=base65536_encode,
    decode=base65536_decode,
    encoded_len=encoded_len,
    max_bytes=max_bytes,
)

register(BASE65536)
