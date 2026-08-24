"""Pure-Python reference implementation of Base32768.

Differential oracle for the C extension. Correctness and readability over
speed; this module is never shipped in the wheel.
"""

from __future__ import annotations

import typing
from types import MappingProxyType

if typing.TYPE_CHECKING:
    from collections.abc import Mapping


BITS_PER_CHAR: typing.Final = 15  # Base32768 is a 15-bit encoding
BITS_PER_BYTE: typing.Final = 8

# alphabet data copied from qntm's base32768 (github.com/qntm/base32768), MIT licensed, copyright qntm.
PAIR_STRINGS: typing.Final[tuple[str, ...]] = (
    "ҠҿԀԟڀڿݠޟ߀ߟကဟႠႿᄀᅟᆀᆟᇠሿበቿዠዿጠጿᎠᏟᐠᙟᚠᛟកសᠠᡟᣀᣟᦀᦟ᧠᧿ᨠᨿᯀᯟᰀᰟᴀᴟ⇠⇿⋀⋟⍀⏟␀␟─❟➀➿⠀⥿⦠⦿⨠⩟⪀⪿⫠⭟ⰀⰟⲀⳟⴀⴟⵀⵟ⺠⻟㇀㇟㐀䶟䷀龿ꀀꑿ꒠꒿ꔀꗿꙀꙟꚠꛟ꜀ꝟꞀꞟꡀꡟ",
    "ƀƟɀʟ",
)


def _build_tables() -> tuple[dict[int, tuple[str, ...]], dict[str, tuple[int, int]]]:
    lookup_e: dict[int, tuple[str, ...]] = {}
    lookup_d: dict[str, tuple[int, int]] = {}

    for r, pair_string in enumerate(PAIR_STRINGS):
        repertoire: list[str] = []
        for i in range(0, len(pair_string), 2):
            first, last = ord(pair_string[i]), ord(pair_string[i + 1])
            repertoire.extend(chr(cp) for cp in range(first, last + 1))

        num_z_bits = BITS_PER_CHAR - BITS_PER_BYTE * r  # 0 -> 15, 1 -> 7
        lookup_e[num_z_bits] = tuple(repertoire)
        for z, char in enumerate(repertoire):
            lookup_d[char] = (num_z_bits, z)

    return lookup_e, lookup_d


_lookup_e, _lookup_d = _build_tables()

LOOKUP_E: typing.Final[Mapping[int, tuple[str, ...]]] = MappingProxyType(_lookup_e)
LOOKUP_D: typing.Final[Mapping[str, tuple[int, int]]] = MappingProxyType(_lookup_d)

del _lookup_e, _lookup_d


def encode(data: bytes) -> str:
    """Encode ``data`` as a Base32768 string."""
    # Setup
    acc = 0  # bit accumulator, most significant bit first
    num_bits = 0  # how many bits currently live in acc
    out: list[str] = []

    # Main loop: 8 bits in, 15 bits out whenever enough have piled up
    for byte in data:
        acc = (acc << BITS_PER_BYTE) | byte
        num_bits += BITS_PER_BYTE

        while num_bits >= BITS_PER_CHAR:
            num_bits -= BITS_PER_CHAR
            out.append(LOOKUP_E[BITS_PER_CHAR][acc >> num_bits])
            acc &= (1 << num_bits) - 1  # drop the bits just consumed

    # Tail: pad the leftovers with 1-bits up to the next available char width
    if num_bits > 0:
        width = 7 if num_bits <= 7 else BITS_PER_CHAR
        gap = width - num_bits
        acc = (acc << gap) | ((1 << gap) - 1)
        out.append(LOOKUP_E[width][acc])

    return "".join(out)


def decode(string: str) -> bytes:
    """Decode a Base32768 string back to bytes.

    Raises:
        ValueError: on a character outside the alphabet; on a 7-bit character
            anywhere but the final position; on a final character that carries
            no payload bits (non-canonical); or on padding bits that are not
            all 1. Every message names the position at fault.
    """
    acc = 0
    num_bits = 0
    out = bytearray()
    last_index = len(string) - 1
    final_num_z_bits = BITS_PER_CHAR  # never trips the check on empty input

    for index, char in enumerate(string):
        entry = LOOKUP_D.get(char)
        if entry is None:
            msg = f"invalid Base32768 character {char!r} (U+{ord(char):04X}) at index {index}"
            raise ValueError(msg)

        num_z_bits, z = entry
        if num_z_bits != BITS_PER_CHAR and index != last_index:
            msg = (
                f"{num_z_bits}-bit character {char!r} at index {index}, "
                + f"only valid at index {last_index}"
            )
            raise ValueError(msg)

        acc = (acc << num_z_bits) | z
        num_bits += num_z_bits
        final_num_z_bits = num_z_bits

        # Drain completed bytes as we go. Letting acc grow to hold the whole
        # payload makes every shift copy a bignum, which is quadratic.
        while num_bits >= BITS_PER_BYTE:
            num_bits -= BITS_PER_BYTE
            out.append((acc >> num_bits) & 0xFF)
            acc &= (1 << num_bits) - 1

    num_pad = num_bits  # 0..7 bits of padding are all that can be left

    # Canonicality: the final character must carry at least one payload bit.
    # A 7-bit final character with 7 padding bits is pure filler, which the
    # encoder never emits (it stops instead of emitting an empty character).
    # Stated width-independently: reject when the final character is no wider
    # than the padding it would have to hold.
    #
    # NOTE: this deliberately diverges from qntm's reference JS, which accepts
    # such a string. radixly rejects it so that decode is injective: one payload,
    # exactly one accepted spelling. Keep this behaviour in the C extension.
    if final_num_z_bits <= num_pad:
        raise ValueError(
            f"non-canonical input: {final_num_z_bits}-bit final character "
            + f"{string[-1]!r} at index {last_index} carries no payload bits"
        )

    # The drain loop masks acc after every byte, so acc holds exactly num_pad
    # bits here. Comparing all of acc — no mask — makes stray high bits
    # (payload that never reached the output) fail this check instead of
    # being silently stripped.
    expected_padding = (1 << num_pad) - 1
    if acc != expected_padding:
        raise ValueError(
            f"expected {num_pad} padding bits set to 1 in final character "
            + f"at index {last_index}, got 0b{acc:0{num_pad}b}"
        )

    return bytes(out)
