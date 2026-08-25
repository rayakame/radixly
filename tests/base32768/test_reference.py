"""Conformance tests for the pure-Python Base32768 reference codec.

Vectors are qntm's official test-data: every ``pairs/*.bin`` payload has a
sibling ``*.txt`` holding its expected encoding, and ``bad/*.txt`` holds
strings that must be rejected. The one exception is ``seven-bit-final``,
generated locally by running qntm's actual JS (see the vectors README) —
his vectors only ever exercise three of the 128 seven-bit characters.
"""

from __future__ import annotations

import copy
import pickle  # ruff: ignore[suspicious-pickle-import] -- tests pickle only their own objects
import typing
import unicodedata

import pytest
from hypothesis import given
from hypothesis import strategies as st

from tests.base32768 import error_cases
from tests.reference import base32768 as base32768_reference
from tests.reference import errors as errors_reference

if typing.TYPE_CHECKING:
    import pathlib

# LOOKUP_D is insertion-ordered: the 15-bit repertoire, then the 7-bit one.
ALPHABET: str = "".join(base32768_reference.LOOKUP_D)

# Everything a transport could mangle: Cs surrogates and Cn unassigned code
# points are not safely transportable; Cc/Cf controls and format characters
# (ZWJ, bidi controls) get stripped or reordered; Zs/Zl/Zp whitespace gets
# trimmed or collapsed; Co private-use has no interoperable meaning;
# Mn/Mc/Me combining marks would merge with a neighbour and change the string.
UNSAFE_CATEGORIES = frozenset({"Cc", "Cf", "Cn", "Co", "Cs", "Mc", "Me", "Mn", "Zl", "Zp", "Zs"})


def test_encode_conformance(base32768_bin_path: pathlib.Path) -> None:
    payload = base32768_bin_path.read_bytes()
    expected = base32768_bin_path.with_suffix(".txt").read_text(encoding="utf-8")
    assert base32768_reference.encode(payload) == expected


def test_decode_conformance(base32768_bin_path: pathlib.Path) -> None:
    payload = base32768_bin_path.read_bytes()
    encoded = base32768_bin_path.with_suffix(".txt").read_text(encoding="utf-8")
    assert base32768_reference.decode(encoded) == payload


@pytest.mark.parametrize("name", sorted(error_cases.BAD_CASES))
def test_decode_rejects_bad_input(name: str, vector_dir: pathlib.Path) -> None:
    bad = (vector_dir / "bad" / f"{name}.txt").read_text(encoding="utf-8")
    with pytest.raises(errors_reference.DecodeError) as exc_info:
        base32768_reference.decode(bad)
    assert exc_info.value.position == error_cases.BAD_CASES[name]


@pytest.mark.parametrize(
    ("string", "position"),
    error_cases.HOSTILE_NON_BMP.values(),
    ids=error_cases.HOSTILE_NON_BMP,
)
def test_decode_rejects_astral_and_surrogate_input(string: str, position: int) -> None:
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
    with pytest.raises(errors_reference.DecodeError) as exc_info:
        base32768_reference.decode(string)
    assert exc_info.value.position == position


@pytest.mark.parametrize(
    ("string", "position"),
    error_cases.CANONICALITY_CASES.values(),
    ids=error_cases.CANONICALITY_CASES,
)
def test_decode_rejects_zero_payload_final_character(string: str, position: int) -> None:
    """The reasoning behind each case lives with the data in error_cases."""
    with pytest.raises(errors_reference.DecodeError) as exc_info:
        base32768_reference.decode(string)
    assert exc_info.value.position == position


def test_decode_accepts_appended_padding_base() -> None:
    """The middle ground the appended-padding case leans on: its valid
    8-character base must itself decode fine, or a blanket "reject every
    7-bit character" bug would pass both canonicality rejections."""
    payload = bytes(15)  # 120 bits, encodes to 8 full characters, no padding
    assert base32768_reference.decode(base32768_reference.encode(payload)) == payload


def test_decode_accepts_canonical_seven_padding_bits() -> None:
    """num_pad == 7 is canonical when the final character is 15-bit."""
    assert base32768_reference.decode(base32768_reference.encode(b"\x00")) == b"\x00"


def test_seven_bit_final_vector_pins_fresh_repertoire(vector_dir: pathlib.Path) -> None:
    """qntm's vectors only ever use z = 47, 63, 127 of the 128 seven-bit
    characters, so a transcription error in the 'ƀƟɀʟ' pair string could
    survive them. The locally generated seven-bit-final vector pins a fourth,
    from the 'ƀ'..'Ɵ' block they never touch. This test guards the vector
    itself: regenerating it from a payload whose encoding does not end in a
    fresh 7-bit character would silently drop that coverage.
    """
    encoded = (vector_dir / "pairs" / "seven-bit-final.txt").read_text(encoding="utf-8")
    num_z_bits, z = base32768_reference.LOOKUP_D[encoded[-1]]
    assert num_z_bits == 7
    assert z < 32, "final character must come from the 'ƀ'..'Ɵ' block"


def test_alphabet_sizes() -> None:
    """A duplicate across repertoires would silently break decode for one z."""
    assert (
        len(base32768_reference.LOOKUP_E[base32768_reference.BITS_PER_CHAR]) == 1 << base32768_reference.BITS_PER_CHAR
    )
    assert len(base32768_reference.LOOKUP_E[7]) == 1 << 7
    assert len(ALPHABET) == (1 << base32768_reference.BITS_PER_CHAR) + (1 << 7)


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


# DecodeError message contract (option c, recorded in CLAUDE.md): None means
# "generate the text", "" is a legal explicit message preserved verbatim.
# test_core.py asserts the same of the C type; only the C enforces the
# str-or-None type — the oracle deliberately trusts its annotations.


def test_decode_error_message_none_generates_text() -> None:
    err = errors_reference.DecodeError(7, message=None)
    assert (str(err), err.message) == ("Decode Error at position 7", "Decode Error at position 7")


def test_decode_error_empty_message_is_preserved() -> None:
    err = errors_reference.DecodeError(3, message="")
    assert (err.message, err.args) == ("", ("",))


@pytest.mark.parametrize("protocol", range(pickle.HIGHEST_PROTOCOL + 1))
@pytest.mark.parametrize("flavor", error_cases.PICKLE_MESSAGE_CASES)
def test_decode_error_pickle_round_trip(flavor: str, protocol: int) -> None:
    """Every view of the clone must agree: type, position (the int, not just
    truthiness), and the message through .message, args, and str() — the last
    is what catches a __setstate__ that fed only one of its two stores."""
    kwargs, expected = error_cases.PICKLE_MESSAGE_CASES[flavor]
    original = errors_reference.DecodeError(error_cases.PICKLE_POSITION, **kwargs)
    clone: object = pickle.loads(pickle.dumps(original, protocol))  # ruff: ignore[suspicious-pickle-usage]  # pyright: ignore[reportAny]
    assert type(clone) is errors_reference.DecodeError
    assert clone.position == error_cases.PICKLE_POSITION
    assert (clone.message, clone.args, str(clone)) == (expected, (expected,), expected)


def test_decode_error_copy() -> None:
    """copy.copy rides __reduce_ex__: nearly free extra coverage."""
    clone = copy.copy(errors_reference.DecodeError(error_cases.PICKLE_POSITION, message="boom"))
    assert type(clone) is errors_reference.DecodeError
    assert (clone.position, clone.message, clone.args, str(clone)) == (
        error_cases.PICKLE_POSITION,
        "boom",
        ("boom",),
        "boom",
    )


@given(st.binary())
def test_round_trip(payload: bytes) -> None:
    assert base32768_reference.decode(base32768_reference.encode(payload)) == payload


def test_vectors_are_present(vector_pairs: tuple[pathlib.Path, ...]) -> None:
    """Guard against an empty parametrize list silently passing the suite."""
    single_bytes = [p for p in vector_pairs if p.parent.name == "single-bytes"]
    assert len(single_bytes) == 256, f"expected 256 single-byte cases, got {len(single_bytes)}"
    assert len(vector_pairs) == 265  # qntm's 264 + the local seven-bit-final vector
