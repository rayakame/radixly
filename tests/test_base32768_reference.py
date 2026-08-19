"""Conformance tests for the pure-Python Base32768 reference codec.

Vectors are qntm's official test-data: every ``pairs/*.bin`` payload has a
sibling ``*.txt`` holding its expected encoding, and ``bad/*.txt`` holds
strings that must be rejected.
"""

import re
import unicodedata
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st
from reference.base32768 import BITS_PER_CHAR, LOOKUP_D, LOOKUP_E, decode, encode

VECTOR_DIR = Path(__file__).parent / "vectors" / "base32768"
PAIRS: list[Path] = sorted((VECTOR_DIR / "pairs").rglob("*.bin"))

# Each bad vector pins both the failure mode and the position it occurs at.
BAD_CASES: dict[str, str] = {
    "bad-padding": "expected 4 padding bits set to 1 at end of input, got 0b0000",
    "bad0": "7-bit character 'ƀ' at index 0, only valid at index 2",
    "not-base32768-char": "invalid Base32768 character 'A' (U+0041) at index 111",
}

PURE_PADDING = LOOKUP_E[7][127]  # 'ʟ', a 7-bit character that is all filler

# LOOKUP_D is insertion-ordered: the 15-bit repertoire, then the 7-bit one.
ALPHABET: str = "".join(LOOKUP_D)

# Cs surrogates and Cn unassigned code points are not safely transportable;
# Mn/Mc/Me combining marks would merge with a neighbour and change the string.
UNSAFE_CATEGORIES = frozenset({"Cs", "Cn", "Mn", "Mc", "Me"})


@pytest.mark.parametrize("bin_path", PAIRS, ids=lambda path: path.stem)
def test_encode_conformance(bin_path: Path) -> None:
    payload = bin_path.read_bytes()
    expected = bin_path.with_suffix(".txt").read_text(encoding="utf-8")
    assert encode(payload) == expected


@pytest.mark.parametrize("bin_path", PAIRS, ids=lambda path: path.stem)
def test_decode_conformance(bin_path: Path) -> None:
    payload = bin_path.read_bytes()
    encoded = bin_path.with_suffix(".txt").read_text(encoding="utf-8")
    assert decode(encoded) == payload


@pytest.mark.parametrize("name", sorted(BAD_CASES), ids=sorted(BAD_CASES))
def test_decode_rejects_bad_input(name: str) -> None:
    bad = (VECTOR_DIR / "bad" / f"{name}.txt").read_text(encoding="utf-8")
    with pytest.raises(ValueError, match=re.escape(BAD_CASES[name])):
        decode(bad)


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
def test_alphabet_is_normalization_stable(form: str) -> None:
    """Encoded text must survive any normalization a transport might apply.

    Joined rather than per-character, so composition across a character
    boundary would show up too.
    """
    assert unicodedata.normalize(form, ALPHABET) == ALPHABET


@given(st.binary())
def test_round_trip(payload: bytes) -> None:
    assert decode(encode(payload)) == payload


def test_vectors_are_present() -> None:
    """Guard against an empty parametrize list silently passing the suite."""
    assert PAIRS
    single_bytes = [p for p in PAIRS if p.parent.name == "single-bytes"]
    assert len(single_bytes) == 256, (
        f"expected 256 single-byte cases, got {len(single_bytes)}"
    )
