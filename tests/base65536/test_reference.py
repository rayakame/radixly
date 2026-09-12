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
"""Conformance against qntm's vectors and the alphabet audit for the base65536 reference."""

from __future__ import annotations

import typing
import unicodedata

import pytest
from hypothesis import given
from hypothesis import strategies as st

from tests.base65536 import error_cases
from tests.reference import base65536 as base65536_reference
from tests.reference import errors as errors_reference

if typing.TYPE_CHECKING:
    import pathlib

ALPHABET: str = "".join(base65536_reference.LOOKUP_D)

UNSAFE_CATEGORIES = frozenset({"Cc", "Cf", "Cn", "Co", "Cs", "Mc", "Me", "Mn", "Zl", "Zp", "Zs"})


def test_encode_conformance(base65536_bin_path: pathlib.Path) -> None:
    payload = base65536_bin_path.read_bytes()
    expected = base65536_bin_path.with_suffix(".txt").read_text(encoding="utf-8")
    assert base65536_reference.encode(payload) == expected


def test_decode_conformance(base65536_bin_path: pathlib.Path) -> None:
    payload = base65536_bin_path.read_bytes()
    encoded = base65536_bin_path.with_suffix(".txt").read_text(encoding="utf-8")
    assert base65536_reference.decode(encoded) == payload


@pytest.mark.parametrize("name", sorted(error_cases.BAD_CASES))
def test_decode_rejects_bad_input(name: str, vector_dir: pathlib.Path) -> None:
    bad = (vector_dir / "bad" / f"{name}.txt").read_text(encoding="utf-8")
    with pytest.raises(errors_reference.DecodeError) as exc_info:
        base65536_reference.decode(bad)
    assert exc_info.value.position == error_cases.BAD_CASES[name]


@pytest.mark.parametrize(
    ("string", "position"),
    error_cases.HOSTILE_CASES.values(),
    ids=error_cases.HOSTILE_CASES,
)
def test_decode_rejects_hostile_input(string: str, position: int) -> None:
    """Rejection pinned here so the C differential has a spec."""
    with pytest.raises(errors_reference.DecodeError) as exc_info:
        base65536_reference.decode(string)
    assert exc_info.value.position == position


@pytest.mark.parametrize(
    ("string", "position"),
    error_cases.TAIL_CASES.values(),
    ids=error_cases.TAIL_CASES,
)
def test_decode_rejects_tail_character_before_the_end(string: str, position: int) -> None:
    """The one-byte block ends the text or fails at its own index; qntm's endOfStreamMidStream vectors pin the same."""
    with pytest.raises(errors_reference.DecodeError) as exc_info:
        base65536_reference.decode(string)
    assert exc_info.value.position == position


@pytest.mark.parametrize("bad", ["text", 42], ids=["str", "int"])
def test_encode_rejects_non_buffer(bad: str | int) -> None:
    """The oracle draws the C's line: buffers in, str out."""
    with pytest.raises(TypeError, match="bytes-like"):
        base65536_reference.encode(bad)  # pyright: ignore[reportArgumentType]


def _type_id(value: object) -> str:
    return type(value).__name__


@pytest.mark.parametrize("bad", error_cases.NON_STR_INPUTS, ids=_type_id)
def test_decode_rejects_non_str(bad: object) -> None:
    with pytest.raises(TypeError, match="expected str, not"):
        base65536_reference.decode(bad)  # pyright: ignore[reportArgumentType]


def test_byte_order_quirk_is_the_wire_format() -> None:
    """The demo from qntm: the second byte picks the block, the first the offset. Swapped, it would still round-trip."""
    assert base65536_reference.encode(b"hello world") == "驨ꍬ啯𒁷ꍲᕤ"
    assert base65536_reference.encode(b"he") == chr(0x9A00 + ord("h"))  # block 101 is U+9A00, 'e' is 101


def test_alphabet_sizes() -> None:
    """A duplicate across repertoires would silently break decode for one z."""
    assert len(base65536_reference.LOOKUP_E[16]) == 1 << 16
    assert len(base65536_reference.LOOKUP_E[8]) == 1 << 8
    assert len(ALPHABET) == (1 << 16) + (1 << 8)


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
    assert base65536_reference.decode(base65536_reference.encode(payload)) == payload


@given(st.binary())
def test_encoded_length(payload: bytes) -> None:
    assert len(base65536_reference.encode(payload)) == (len(payload) + 1) // 2


def test_vectors_are_present(vector_pairs: tuple[pathlib.Path, ...], vector_dir: pathlib.Path) -> None:
    """Guard against an empty parametrize list silently passing the suite, and a bad vector nobody pinned."""
    single_bytes = [p for p in vector_pairs if p.parent.name == "single-bytes"]
    doubled_bytes = [p for p in vector_pairs if p.parent.name == "doubled-bytes"]
    assert len(single_bytes) == 256, f"expected 256 single-byte cases, got {len(single_bytes)}"
    assert len(doubled_bytes) == 256, f"expected 256 doubled-byte cases, got {len(doubled_bytes)}"
    assert len(vector_pairs) == 521  # qntm's complete pairs set
    assert sorted(error_cases.BAD_CASES) == sorted(p.stem for p in (vector_dir / "bad").glob("*.txt"))
