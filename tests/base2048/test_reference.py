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
"""Conformance against qntm's vectors and the alphabet audit for the base2048 reference."""

from __future__ import annotations

import typing
import unicodedata

import pytest
from hypothesis import given
from hypothesis import strategies as st

from tests.base2048 import error_cases
from tests.reference import base2048 as base2048_reference
from tests.reference import errors as errors_reference

if typing.TYPE_CHECKING:
    import pathlib

ALPHABET: str = "".join(base2048_reference.LOOKUP_D)

UNSAFE_CATEGORIES = frozenset({"Cc", "Cf", "Cn", "Co", "Cs", "Mc", "Me", "Mn", "Zl", "Zp", "Zs"})


def test_encode_conformance(base2048_bin_path: pathlib.Path) -> None:
    payload = base2048_bin_path.read_bytes()
    expected = base2048_bin_path.with_suffix(".txt").read_text(encoding="utf-8")
    assert base2048_reference.encode(payload) == expected


def test_decode_conformance(base2048_bin_path: pathlib.Path) -> None:
    payload = base2048_bin_path.read_bytes()
    encoded = base2048_bin_path.with_suffix(".txt").read_text(encoding="utf-8")
    assert base2048_reference.decode(encoded) == payload


@pytest.mark.parametrize("name", sorted(error_cases.BAD_CASES))
def test_decode_rejects_bad_input(name: str, vector_dir: pathlib.Path) -> None:
    bad = (vector_dir / "bad" / f"{name}.txt").read_text(encoding="utf-8")
    with pytest.raises(errors_reference.DecodeError) as exc_info:
        base2048_reference.decode(bad)
    assert exc_info.value.position == error_cases.BAD_CASES[name]


@pytest.mark.parametrize(
    ("string", "position"),
    error_cases.HOSTILE_CASES.values(),
    ids=error_cases.HOSTILE_CASES,
)
def test_decode_rejects_hostile_input(string: str, position: int) -> None:
    """Rejection pinned here so the C differential has a spec."""
    with pytest.raises(errors_reference.DecodeError) as exc_info:
        base2048_reference.decode(string)
    assert exc_info.value.position == position


@pytest.mark.parametrize(
    ("string", "position"),
    error_cases.PADDING_CASES.values(),
    ids=error_cases.PADDING_CASES,
)
def test_decode_rejects_zeroed_padding(string: str, position: int) -> None:
    with pytest.raises(errors_reference.DecodeError) as exc_info:
        base2048_reference.decode(string)
    assert exc_info.value.position == position


@pytest.mark.parametrize(
    ("string", "position"),
    error_cases.SHORT_CASES.values(),
    ids=error_cases.SHORT_CASES,
)
def test_decode_rejects_short_character_before_the_end(string: str, position: int) -> None:
    with pytest.raises(errors_reference.DecodeError) as exc_info:
        base2048_reference.decode(string)
    assert exc_info.value.position == position


@pytest.mark.parametrize(
    ("string", "position"),
    error_cases.CANONICALITY_CASES.values(),
    ids=error_cases.CANONICALITY_CASES,
)
def test_decode_rejects_zero_payload_final_character(string: str, position: int) -> None:
    """The reasoning behind each case lives with the data in error_cases."""
    with pytest.raises(errors_reference.DecodeError) as exc_info:
        base2048_reference.decode(string)
    assert exc_info.value.position == position


def test_decode_accepts_appended_padding_base() -> None:
    """The appended-padding case's base must decode on its own, or its rejection proves nothing."""
    payload = bytes(11)  # 88 bits, encodes to 8 full characters, no padding
    assert base2048_reference.decode(base2048_reference.encode(payload)) == payload


def test_decode_accepts_canonical_seven_padding_bits() -> None:
    """Six bytes leave 4 bits: an 11-bit final character with 7 padding bits is the widest canonical padding."""
    assert base2048_reference.decode(base2048_reference.encode(bytes(6))) == bytes(6)


@pytest.mark.parametrize("z", range(8))
def test_short_alphabet_from_first_principles(z: int) -> None:
    """Ten bytes leave exactly 3 bits, the low bits of the last byte; the vectors only ever hit one of the eight."""
    assert base2048_reference.encode(bytes(9) + bytes([z]))[-1] == chr(ord("0") + z)


@pytest.mark.parametrize("bad", ["text", 42], ids=["str", "int"])
def test_encode_rejects_non_buffer(bad: str | int) -> None:
    """The oracle draws the C's line: buffers in, str out."""
    with pytest.raises(TypeError, match="bytes-like"):
        base2048_reference.encode(bad)  # pyright: ignore[reportArgumentType]


def _type_id(value: object) -> str:
    return type(value).__name__


@pytest.mark.parametrize("bad", error_cases.NON_STR_INPUTS, ids=_type_id)
def test_decode_rejects_non_str(bad: object) -> None:
    with pytest.raises(TypeError, match="expected str, not"):
        base2048_reference.decode(bad)  # pyright: ignore[reportArgumentType]


def test_decode_accepts_canonical_short_final_character() -> None:
    """Two bytes leave 5 bits, three leave 2: the second case is the short alphabet doing real work."""
    assert base2048_reference.encode(b"\x00\x00\x00")[-1] in base2048_reference.LOOKUP_E[3]
    assert base2048_reference.decode(base2048_reference.encode(b"\x00\x00\x00")) == b"\x00\x00\x00"


@pytest.mark.parametrize(("payload", "expected"), list(error_cases.NARROW_PINS.items()), ids=repr)
def test_narrow_pins(payload: bytes, expected: str) -> None:
    """Single bytes 0 to 6 pad to indexes below 63, the repertoire's Latin-1 run; the C test pins the same strings."""
    assert base2048_reference.encode(payload) == expected


def test_alphabet_sizes() -> None:
    """A duplicate across repertoires would silently break decode for one z."""
    assert len(base2048_reference.LOOKUP_E[base2048_reference.BITS_PER_CHAR]) == 1 << base2048_reference.BITS_PER_CHAR
    assert len(base2048_reference.LOOKUP_E[3]) == 1 << 3
    assert len(ALPHABET) == (1 << base2048_reference.BITS_PER_CHAR) + (1 << 3)


def test_alphabet_top_is_the_c_table_end() -> None:
    """The C's MAX_CHAR is 0x1055 and its reverse table ends there; the alphabet's top must be that cell."""
    assert max(map(ord, ALPHABET)) == 0x1055


def test_alphabet_has_no_unsafe_characters() -> None:
    """A mangled pair string would shift a whole range; Cn re-audits per interpreter."""
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
    """Joined rather than per-character, so cross-boundary composition shows too."""
    assert unicodedata.normalize(form, ALPHABET) == ALPHABET


@given(st.binary())
def test_round_trip(payload: bytes) -> None:
    assert base2048_reference.decode(base2048_reference.encode(payload)) == payload


def test_vectors_are_present(vector_pairs: tuple[pathlib.Path, ...], vector_dir: pathlib.Path) -> None:
    """Guard against an empty parametrize list silently passing the suite, and a bad vector nobody pinned."""
    single_bytes = [p for p in vector_pairs if p.parent.name == "single-bytes"]
    assert len(single_bytes) == 256, f"expected 256 single-byte cases, got {len(single_bytes)}"
    assert len(vector_pairs) == 264  # qntm's complete pairs set
    assert sorted(error_cases.BAD_CASES) == sorted(p.stem for p in (vector_dir / "bad").glob("*.txt"))
