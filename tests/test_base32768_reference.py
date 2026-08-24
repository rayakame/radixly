"""Conformance tests for the pure-Python Base32768 reference codec.

Vectors are qntm's official test-data: every ``pairs/*.bin`` payload has a
sibling ``*.txt`` holding its expected encoding, and ``bad/*.txt`` holds
strings that must be rejected. The one exception is ``seven-bit-final``,
generated locally by running qntm's actual JS (see the vectors README) —
his vectors only ever exercise three of the 128 seven-bit characters.
"""

from __future__ import annotations

import re
import typing
import unicodedata

import pytest
from hypothesis import given
from hypothesis import strategies as st
from reference.base32768 import BITS_PER_CHAR
from reference.base32768 import LOOKUP_D
from reference.base32768 import LOOKUP_E
from reference.base32768 import decode
from reference.base32768 import encode

if typing.TYPE_CHECKING:
    import pathlib

# Each bad vector pins both the failure mode and the position it occurs at.
BAD_CASES: dict[str, str] = {
    "bad-padding": "expected 4 padding bits set to 1 in final character at index 3, got 0b0000",
    "bad0": "7-bit character 'ƀ' at index 0, only valid at index 2",
    "not-base32768-char": "invalid Base32768 character 'A' (U+0041) at index 111",
}

PURE_PADDING = LOOKUP_E[7][127]  # 'ʟ', a 7-bit character that is all filler

# LOOKUP_D is insertion-ordered: the 15-bit repertoire, then the 7-bit one.
ALPHABET: str = "".join(LOOKUP_D)

# Everything a transport could mangle: Cs surrogates and Cn unassigned code
# points are not safely transportable; Cc/Cf controls and format characters
# (ZWJ, bidi controls) get stripped or reordered; Zs/Zl/Zp whitespace gets
# trimmed or collapsed; Co private-use has no interoperable meaning;
# Mn/Mc/Me combining marks would merge with a neighbour and change the string.
UNSAFE_CATEGORIES = frozenset({"Cc", "Cf", "Cn", "Co", "Cs", "Mc", "Me", "Mn", "Zl", "Zp", "Zs"})


def test_encode_conformance(base32768_bin_path: pathlib.Path) -> None:
    payload = base32768_bin_path.read_bytes()
    expected = base32768_bin_path.with_suffix(".txt").read_text(encoding="utf-8")
    assert encode(payload) == expected


def test_decode_conformance(base32768_bin_path: pathlib.Path) -> None:
    payload = base32768_bin_path.read_bytes()
    encoded = base32768_bin_path.with_suffix(".txt").read_text(encoding="utf-8")
    assert decode(encoded) == payload


@pytest.mark.parametrize("name", sorted(BAD_CASES))
def test_decode_rejects_bad_input(name: str, vector_dir: pathlib.Path) -> None:
    bad = (vector_dir / "bad" / f"{name}.txt").read_text(encoding="utf-8")
    with pytest.raises(ValueError, match=re.escape(BAD_CASES[name])):
        decode(bad)


VALID_8_CHARS = encode(bytes(15))  # 120 bits: 8 full 15-bit characters, no padding

HOSTILE_NON_BMP: dict[str, tuple[str, str]] = {
    "astral": (
        "\U0001f600",
        "invalid Base32768 character '😀' (U+1F600) at index 0",
    ),
    "high-surrogate": (
        "\ud800",
        "invalid Base32768 character '\\ud800' (U+D800) at index 0",
    ),
    "low-surrogate": (
        "\udfff",
        "invalid Base32768 character '\\udfff' (U+DFFF) at index 0",
    ),
    "astral-mid-string": (
        VALID_8_CHARS + "\U0001f600" + VALID_8_CHARS,
        "invalid Base32768 character '😀' (U+1F600) at index 8",
    ),
    "surrogate-mid-string": (
        VALID_8_CHARS + "\udc00" + VALID_8_CHARS,
        "invalid Base32768 character '\\udc00' (U+DC00) at index 8",
    ),
}


@pytest.mark.parametrize(("string", "message"), HOSTILE_NON_BMP.values(), ids=HOSTILE_NON_BMP)
def test_decode_rejects_astral_and_surrogate_input(string: str, message: str) -> None:
    """Astral characters and lone surrogates must be rejected with a position.

    The alphabet is BMP-only by design, so both are invalid by definition —
    but they stress two different parts of the C decoder's defense (M4): a
    lone surrogate's code point is below 0x10000 and goes through the reverse
    table, relying on those 2048 entries being -1, while an astral code point
    would index past the table entirely, relying on the cp < 0x10000 bounds
    guard. The differential harness asserts C rejects the same inputs at the
    same positions as the reference, which only means something on non-BMP
    input once the reference has pinned what rejection looks like here.
    """
    with pytest.raises(ValueError, match=re.escape(message)):
        decode(string)


def test_decode_rejects_lone_padding_character() -> None:
    """A 7-bit character with no payload bits is not a valid encoding of b""."""
    with pytest.raises(ValueError, match=r"7-bit final character .* at index 0"):
        decode(PURE_PADDING)


def test_decode_rejects_appended_padding_character() -> None:
    """The sneaky cousin: valid encoding + 'ʟ' would decode to the same payload
    under qntm's rules, and is rejected here instead.

    A blanket "reject every 7-bit character" bug would also pass the lone-'ʟ'
    test above, so this pins the middle ground: the unextended encoding must
    still decode fine.
    """
    payload = bytes(15)  # 120 bits, encodes to 8 full characters, no padding
    encoded = encode(payload)
    assert decode(encoded) == payload  # unchanged, and still canonical

    with pytest.raises(ValueError, match=r"7-bit final character .* at index 8"):
        decode(encoded + PURE_PADDING)


def test_decode_accepts_canonical_seven_padding_bits() -> None:
    """num_pad == 7 is canonical when the final character is 15-bit."""
    assert decode(encode(b"\x00")) == b"\x00"


def test_seven_bit_final_vector_pins_fresh_repertoire(vector_dir: pathlib.Path) -> None:
    """qntm's vectors only ever use z = 47, 63, 127 of the 128 seven-bit
    characters, so a transcription error in the 'ƀƟɀʟ' pair string could
    survive them. The locally generated seven-bit-final vector pins a fourth,
    from the 'ƀ'..'Ɵ' block they never touch. This test guards the vector
    itself: regenerating it from a payload whose encoding does not end in a
    fresh 7-bit character would silently drop that coverage.
    """
    encoded = (vector_dir / "pairs" / "seven-bit-final.txt").read_text(encoding="utf-8")
    num_z_bits, z = LOOKUP_D[encoded[-1]]
    assert num_z_bits == 7
    assert z < 32, "final character must come from the 'ƀ'..'Ɵ' block"


def test_alphabet_sizes() -> None:
    """A duplicate across repertoires would silently break decode for one z."""
    assert len(LOOKUP_E[BITS_PER_CHAR]) == 1 << BITS_PER_CHAR
    assert len(LOOKUP_E[7]) == 1 << 7
    assert len(ALPHABET) == (1 << BITS_PER_CHAR) + (1 << 7)


def test_alphabet_has_no_unsafe_characters() -> None:
    """A mangled pair string would silently shift a whole code point range.

    Cn is interpreter-version-sensitive by design: it also flags a code point
    that was assigned when the alphabet was written but is not any more.
    """
    offenders = {
        f"U+{ord(char):04X}": unicodedata.category(char)
        for char in ALPHABET
        if unicodedata.category(char) in UNSAFE_CATEGORIES
    }
    assert not offenders, f"unsafe characters in alphabet: {offenders}"


@pytest.mark.parametrize("form", ["NFC", "NFD", "NFKC", "NFKD"])
def test_alphabet_is_normalization_stable(
    form: typing.Literal["NFC", "NFD", "NFKC", "NFKD"],
) -> None:
    """Encoded text must survive any normalization a transport might apply.

    Joined rather than per-character, so composition across a character
    boundary would show up too.
    """
    assert unicodedata.normalize(form, ALPHABET) == ALPHABET


@given(st.binary())
def test_round_trip(payload: bytes) -> None:
    assert decode(encode(payload)) == payload


def test_vectors_are_present(vector_pairs: tuple[pathlib.Path]) -> None:
    """Guard against an empty parametrize list silently passing the suite."""
    single_bytes = [p for p in vector_pairs if p.parent.name == "single-bytes"]
    assert len(single_bytes) == 256, f"expected 256 single-byte cases, got {len(single_bytes)}"
    assert len(vector_pairs) == 265  # qntm's 264 + the local seven-bit-final vector
