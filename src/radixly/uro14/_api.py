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
"""Public face of the uro14 codec; the package ``__init__`` re-exports everything here."""

from __future__ import annotations

from radixly._codec import Codec
from radixly._codec import register
from radixly._core import uro14_decode
from radixly._core import uro14_encode

__all__ = ("BITS_PER_CHAR", "URO14", "decode", "encode", "encoded_len", "max_bytes")

encode = uro14_encode
decode = uro14_decode

BITS_PER_CHAR = 14
"""Payload bits carried by one body character; the length prefix is one character on top."""


def encoded_len(num_bytes: int) -> int:
    """Exact length of ``encode(data)``: the prefix plus the body.

    Parameters
    ----------
    num_bytes
        Payload size in bytes.

    Returns
    -------
    int
        ``1 + ceil(8 * num_bytes / 14)``.

    Raises
    ------
    ValueError
        If ``num_bytes`` is negative.

    Examples
    --------
    >>> from radixly import uro14
    >>> uro14.encoded_len(10)
    7
    """
    if num_bytes < 0:
        msg = f"num_bytes must be >= 0, got {num_bytes}"
        raise ValueError(msg)
    return 1 + (8 * num_bytes + 13) // BITS_PER_CHAR


def max_bytes(num_chars: int) -> int:
    """Largest payload that fits in ``num_chars`` characters.

    Zero characters fit nothing, the prefix alone needs one, so ``max_bytes(0)`` refuses.

    Parameters
    ----------
    num_chars
        The limit, in code points, prefix included.

    Returns
    -------
    int
        ``floor(14 * (num_chars - 1) / 8)``.

    Raises
    ------
    ValueError
        If ``num_chars`` is negative or zero.

    Examples
    --------
    >>> from radixly import uro14
    >>> uro14.max_bytes(100)
    173
    """
    if num_chars < 0:
        msg = f"num_chars must be >= 0, got {num_chars}"
        raise ValueError(msg)
    if num_chars == 0:
        msg = "no payload fits in 0 characters: the length prefix needs one"
        raise ValueError(msg)
    return BITS_PER_CHAR * (num_chars - 1) // 8


URO14 = Codec(
    name="uro14",
    bits_per_char=BITS_PER_CHAR,
    encode=uro14_encode,
    decode=uro14_decode,
    encoded_len=encoded_len,
    max_bytes=max_bytes,
)

register(URO14)
