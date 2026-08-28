"""Reference for contiguous-block codecs: one alphabet run, bits_per_char per character."""

from __future__ import annotations

from tests.reference import errors
from tests.reference import shared


def encode(data: bytes, start: int, bits_per_char: int) -> str:
    """Encode data with bits_per_char per character, alphabet starting at start."""
    acc = 0  # bit accumulator, most significant bit first
    num_bits = 0  # how many bits currently live in acc
    out: list[str] = []

    for byte in data:
        acc = (acc << shared.BITS_PER_BYTE) | byte
        num_bits += shared.BITS_PER_BYTE

        while num_bits >= bits_per_char:
            num_bits -= bits_per_char
            out.append(chr(start + (acc >> num_bits)))
            acc &= (1 << num_bits) - 1

    if num_bits > 0:
        gap = bits_per_char - num_bits
        acc = (acc << gap) | ((1 << gap) - 1)
        out.append(chr(start + acc))

    return "".join(out)


def decode(string: str, start: int, bits_per_char: int) -> bytes:
    """Decode strictly; DecodeError (with position) on anything invalid or non-canonical."""
    acc = 0
    num_bits = 0
    out = bytearray()
    last_index = len(string) - 1
    limit = 1 << bits_per_char

    for index, char in enumerate(string):
        value = ord(char) - start
        if not (0 <= value < limit):
            msg = f"invalid character {char!r} (U+{ord(char):04X}) at index {index}"
            raise errors.DecodeError(index, message=msg)
        acc = (acc << bits_per_char) | value
        num_bits += bits_per_char

        while num_bits >= shared.BITS_PER_BYTE:
            num_bits -= shared.BITS_PER_BYTE
            out.append(acc >> num_bits)
            acc &= (1 << num_bits) - 1

    num_pad = num_bits
    # Canonicality (fixed decision, mirrors base32768): the final character
    # must carry at least one payload bit.
    if bits_per_char <= num_pad:
        msg = (
            f"non-canonical input: {bits_per_char}-bit final character "
            + f"{string[-1]!r} at index {last_index} carries no payload bits"
        )
        raise errors.DecodeError(last_index, message=msg)

    # acc holds exactly num_pad bits here; comparing it unmasked makes stray bits fail.
    expected_padding = (1 << num_pad) - 1
    if acc != expected_padding:
        msg = (
            f"expected {num_pad} padding bits set to 1 in final character at index {last_index}, "
            + f"got 0b{acc:0{num_pad}b}"
        )
        raise errors.DecodeError(last_index, message=msg)

    return bytes(out)
