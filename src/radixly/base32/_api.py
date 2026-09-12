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
"""Public face of the base32 codec; the package ``__init__`` re-exports everything here."""

from __future__ import annotations

from radixly._codec import Codec
from radixly._codec import register
from radixly._core import base32_decode
from radixly._core import base32_encode

__all__ = ("BASE32", "BITS_PER_CHAR", "decode", "encode", "encoded_len", "max_bytes")

encode = base32_encode
decode = base32_decode

BITS_PER_CHAR = 5
"""Payload bits per character; a final group is padded with ``=`` to eight characters."""


def encoded_len(num_bytes: int) -> int:
    """Exact length of ``encode(data)`` for ``num_bytes`` bytes, without encoding.

    Parameters
    ----------
    num_bytes
        Payload size in bytes.

    Returns
    -------
    int
        ``8 * ceil(num_bytes / 5)``.

    Raises
    ------
    ValueError
        If ``num_bytes`` is negative.

    Examples
    --------
    >>> from radixly import base32
    >>> base32.encoded_len(10)
    16
    """
    if num_bytes < 0:
        msg = f"num_bytes must be >= 0, got {num_bytes}"
        raise ValueError(msg)
    return 8 * ((num_bytes + 4) // 5)


def max_bytes(num_chars: int) -> int:
    """Largest payload that fits in ``num_chars`` characters.

    Parameters
    ----------
    num_chars
        The limit, in code points.

    Returns
    -------
    int
        ``5 * floor(num_chars / 8)``.

    Raises
    ------
    ValueError
        If ``num_chars`` is negative.

    Examples
    --------
    >>> from radixly import base32
    >>> base32.max_bytes(100)
    60
    """
    if num_chars < 0:
        msg = f"num_chars must be >= 0, got {num_chars}"
        raise ValueError(msg)
    return 5 * (num_chars // 8)


BASE32 = Codec(
    name="base32",
    bits_per_char=BITS_PER_CHAR,
    encode=base32_encode,
    decode=base32_decode,
    encoded_len=encoded_len,
    max_bytes=max_bytes,
)

register(BASE32)
