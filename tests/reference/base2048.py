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
"""Pure-Python reference for base2048, the oracle for the C. Never shipped."""

from __future__ import annotations

import types
import typing

from tests.reference import errors
from tests.reference import shared

if typing.TYPE_CHECKING:
    from collections.abc import Mapping

    from _typeshed import ReadableBuffer

__all__ = ("BITS_PER_CHAR", "LOOKUP_D", "LOOKUP_E", "PAIR_STRINGS", "SHORT_BITS", "decode", "encode")

BITS_PER_CHAR: typing.Final = 11
SHORT_BITS: typing.Final = BITS_PER_CHAR - shared.BITS_PER_BYTE  # the 3-bit tail alphabet

# Alphabet data from qntm's base2048 (github.com/qntm/base2048), MIT, copyright qntm.
PAIR_STRINGS: typing.Final[tuple[str, ...]] = (
    "89AZazÆÆÐÐØØÞßææððøøþþĐđĦħııĸĸŁłŊŋŒœŦŧƀƟƢƮƱǃǝǝǤǥǶǷȜȝȠȥȴʯͰͳͶͷͻͽͿͿΑΡΣΩαωϏϏϗϯϳϳϷϸϺϿЂЂЄІЈЋЏИКикяђђєіјћџѵѸҁҊӀӃӏӔӕӘәӠӡӨөӶӷӺԯԱՖաֆאתװײؠءاؿفي٠٩ٮٯٱٴٹڿہہۃےەەۮۼۿۿܐܐܒܯݍޥޱޱ߀ߪࠀࠕࡀࡘࡠࡪࢠࢴࢶࢽऄनपरलळवहऽऽॐॐॠॡ०९ॲঀঅঌএঐওনপরললশহঽঽৎৎৠৡ০ৱ৴৹ৼৼਅਊਏਐਓਨਪਰਲਲਵਵਸਹੜੜ੦੯ੲੴઅઍએઑઓનપરલળવહઽઽૐૐૠૡ૦૯ૹૹଅଌଏଐଓନପରଲଳଵହଽଽୟୡ୦୯ୱ୷ஃஃஅஊஎஐஒஓககஙசஜஜஞடணதநபமஹௐௐ௦௲అఌఎఐఒనపహఽఽౘౚౠౡ౦౯౸౾ಀಀಅಌಎಐಒನಪಳವಹಽಽೞೞೠೡ೦೯ೱೲഅഌഎഐഒഺഽഽൎൎൔൖ൘ൡ൦൸ൺൿඅඖකනඳරලලවෆ෦෯กะาาเๅ๐๙ກຂຄຄງຈຊຊຍຍດທນຟມຣລລວວສຫອະາາຽຽເໄ໐໙ໞໟༀༀ༠༳ཀགངཇཉཌཎདནབམཛཝཨཪཬྈྌကဥဧဪဿ၉ၐၕ",  # ruff: ignore[ambiguous-unicode-character-string]
    "07",
)


def _build_tables() -> tuple[dict[int, tuple[str, ...]], dict[str, tuple[int, int]]]:
    lookup_e: dict[int, tuple[str, ...]] = {}
    lookup_d: dict[str, tuple[int, int]] = {}

    for r, pair_string in enumerate(PAIR_STRINGS):
        repertoire: list[str] = []
        for i in range(0, len(pair_string), 2):
            first, last = ord(pair_string[i]), ord(pair_string[i + 1])
            repertoire.extend(chr(cp) for cp in range(first, last + 1))

        num_z_bits = BITS_PER_CHAR - shared.BITS_PER_BYTE * r  # 0 -> 11, 1 -> 3
        lookup_e[num_z_bits] = tuple(repertoire)
        for z, char in enumerate(repertoire):
            lookup_d[char] = (num_z_bits, z)

    return lookup_e, lookup_d


_lookup_e, _lookup_d = _build_tables()

LOOKUP_E: typing.Final[Mapping[int, tuple[str, ...]]] = types.MappingProxyType(_lookup_e)
LOOKUP_D: typing.Final[Mapping[str, tuple[int, int]]] = types.MappingProxyType(_lookup_d)

del _lookup_e, _lookup_d


def _as_bytes(data: ReadableBuffer) -> bytes:
    """Draw the C's line: any buffer is accepted, and memoryview refuses str with the same words."""
    return bytes(memoryview(data))


def _require_str(string: object) -> None:
    if not isinstance(string, str):
        msg = f"expected str, not {type(string).__name__}"
        raise TypeError(msg)


def encode(data: ReadableBuffer) -> str:
    """Encode ``data`` as a Base2048 string; any buffer is accepted, ``str`` is not."""
    data = _as_bytes(data)
    acc = 0
    num_bits = 0
    out: list[str] = []

    # Main loop: 8 bits in, 11 bits out whenever enough have piled up
    for byte in data:
        acc = (acc << shared.BITS_PER_BYTE) | byte
        num_bits += shared.BITS_PER_BYTE

        while num_bits >= BITS_PER_CHAR:
            num_bits -= BITS_PER_CHAR
            out.append(LOOKUP_E[BITS_PER_CHAR][acc >> num_bits])
            acc &= (1 << num_bits) - 1  # drop the bits just consumed

    # Tail: pad the leftovers with 1-bits up to the next available char width
    if num_bits > 0:
        width = SHORT_BITS if num_bits <= SHORT_BITS else BITS_PER_CHAR
        gap = width - num_bits
        acc = (acc << gap) | ((1 << gap) - 1)
        out.append(LOOKUP_E[width][acc])

    return "".join(out)


def decode(string: str) -> bytes:
    """Decode a Base2048 string back to bytes.

    Raises
    ------
    errors.DecodeError
        Invalid character, 3-bit character not last, no-payload final character,
        or padding not all ones; position names the culprit.
    """
    _require_str(string)
    acc = 0
    num_bits = 0
    out = bytearray()
    last_index = len(string) - 1
    final_num_z_bits = BITS_PER_CHAR  # never trips the check on empty input

    for index, char in enumerate(string):
        entry = LOOKUP_D.get(char)
        if entry is None:
            msg = f"invalid Base2048 character {char!r} (U+{ord(char):04X}) at index {index}"
            raise errors.DecodeError(index, message=msg)

        num_z_bits, z = entry
        if num_z_bits != BITS_PER_CHAR and index != last_index:
            msg = f"{num_z_bits}-bit character {char!r} at index {index}, only valid at index {last_index}"
            raise errors.DecodeError(index, message=msg)

        acc = (acc << num_z_bits) | z
        num_bits += num_z_bits
        final_num_z_bits = num_z_bits

        # Drain bytes as we go; a whole-payload bignum makes every shift quadratic.
        while num_bits >= shared.BITS_PER_BYTE:
            num_bits -= shared.BITS_PER_BYTE
            out.append(acc >> num_bits)
            acc &= (1 << num_bits) - 1

    num_pad = num_bits  # 0..7 bits of padding are all that can be left

    # Canonicality: the final char must carry a payload bit. Stricter than qntm's JS on purpose; keep the C in lockstep.
    if final_num_z_bits <= num_pad:
        msg = (
            f"non-canonical input: {final_num_z_bits}-bit final character "
            + f"{string[-1]!r} at index {last_index} carries no payload bits"
        )
        raise errors.DecodeError(last_index, message=msg)

    # acc holds exactly num_pad bits here; comparing it unmasked catches stray high bits.
    expected_padding = (1 << num_pad) - 1
    if acc != expected_padding:
        msg = (
            f"expected {num_pad} padding bits set to 1 in final character at index {last_index}, "
            + f"got 0b{acc:0{num_pad}b}"
        )
        raise errors.DecodeError(last_index, message=msg)

    return bytes(out)
