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
"""Pure-Python reference for base65536, the oracle for the C. Never shipped."""

from __future__ import annotations

import types
import typing

from tests.reference import errors
from tests.reference import shared

if typing.TYPE_CHECKING:
    from collections.abc import Mapping

    from _typeshed import ReadableBuffer

__all__ = ("BITS_PER_CHAR", "LOOKUP_D", "LOOKUP_E", "PAIR_STRINGS", "decode", "encode")

BITS_PER_CHAR: typing.Final = 16

# Block data from qntm's base65536 (github.com/qntm/base65536), MIT, copyright qntm.
PAIR_STRINGS: typing.Final[tuple[str, ...]] = (
    "㐀䳿一黿ꄀꏿꔀꗿ𐘀𐛿𒀀𒋿𓀀𓏿𔐀𔗿𖠀𖧿𠀀𨗿",
    "ᔀᗿ",
)


def _build_tables() -> tuple[dict[int, tuple[str, ...]], dict[str, tuple[int, int]]]:
    lookup_e: dict[int, tuple[str, ...]] = {}
    lookup_d: dict[str, tuple[int, int]] = {}

    for r, pair_string in enumerate(PAIR_STRINGS):
        repertoire: list[str] = []
        for i in range(0, len(pair_string), 2):
            first, last = ord(pair_string[i]), ord(pair_string[i + 1])
            repertoire.extend(chr(cp) for cp in range(first, last + 1))

        num_z_bits = BITS_PER_CHAR - shared.BITS_PER_BYTE * r  # 0 -> 16, 1 -> 8
        table: list[str] = [""] * len(repertoire)
        for z2, char in enumerate(repertoire):
            # qntm's quirk, kept for wire compatibility: the 16-bit repertoire is walked with the bytes swapped,
            # so the second byte picks the 256-code-point block and the first byte the offset inside it.
            z = 256 * (z2 % 256) + (z2 >> 8) if num_z_bits == BITS_PER_CHAR else z2
            table[z] = char
            lookup_d[char] = (num_z_bits, z)
        lookup_e[num_z_bits] = tuple(table)

    return lookup_e, lookup_d


_lookup_e, _lookup_d = _build_tables()

LOOKUP_E: typing.Final[Mapping[int, tuple[str, ...]]] = types.MappingProxyType(_lookup_e)
LOOKUP_D: typing.Final[Mapping[str, tuple[int, int]]] = types.MappingProxyType(_lookup_d)

del _lookup_e, _lookup_d


def _as_bytes(data: ReadableBuffer) -> bytes:
    """Draw the C's line: any contiguous buffer is accepted, str and strided views are refused."""
    view = memoryview(data)  # refuses str with the C's words
    if not view.c_contiguous:
        msg = "memoryview: underlying buffer is not C-contiguous"
        raise BufferError(msg)
    return view.tobytes()


def _require_str(string: object) -> None:
    if not isinstance(string, str):
        msg = f"expected str, not {type(string).__name__}"
        raise TypeError(msg)


def encode(data: ReadableBuffer) -> str:
    """Encode ``data`` as a Base65536 string; any buffer is accepted, ``str`` is not."""
    data = _as_bytes(data)
    acc = 0
    num_bits = 0
    out: list[str] = []

    # Main loop: 8 bits in, one character out for every 16
    for byte in data:
        acc = (acc << shared.BITS_PER_BYTE) | byte
        num_bits += shared.BITS_PER_BYTE

        if num_bits == BITS_PER_CHAR:
            out.append(LOOKUP_E[BITS_PER_CHAR][acc])
            acc = 0
            num_bits = 0

    # Tail: a lone byte goes into the 8-bit block; nothing needs padding since 8 divides 16.
    if num_bits > 0:
        out.append(LOOKUP_E[shared.BITS_PER_BYTE][acc])

    return "".join(out)


def decode(string: str) -> bytes:
    """Decode a Base65536 string back to bytes.

    Raises
    ------
    errors.DecodeError
        Invalid character, or an 8-bit character anywhere but last; position names the culprit.
    """
    _require_str(string)
    out = bytearray()
    last_index = len(string) - 1

    for index, char in enumerate(string):
        entry = LOOKUP_D.get(char)
        if entry is None:
            msg = f"invalid Base65536 character {char!r} (U+{ord(char):04X}) at index {index}"
            raise errors.DecodeError(index, message=msg)

        num_z_bits, z = entry
        if num_z_bits != BITS_PER_CHAR and index != last_index:
            msg = f"{num_z_bits}-bit character {char!r} at index {index}, only valid at index {last_index}"
            raise errors.DecodeError(index, message=msg)

        if num_z_bits == BITS_PER_CHAR:
            out.append(z >> shared.BITS_PER_BYTE)
        out.append(z & 0xFF)

    return bytes(out)
