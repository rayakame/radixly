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
"""Conformance and differential tests for the C base2048 codec."""

from __future__ import annotations

import inspect
import random
import typing

if typing.TYPE_CHECKING:
    import pathlib
    from collections.abc import Callable

    from _typeshed import ReadableBuffer

import pytest
from hypothesis import given
from hypothesis import strategies as st

from radixly import _core
from tests.base2048 import error_cases
from tests.payloads import PAYLOAD_FLAVORS
from tests.reference import base2048 as base2048_reference


def test_encode_conformance(base2048_bin_path: pathlib.Path) -> None:
    payload = base2048_bin_path.read_bytes()
    expected = base2048_bin_path.with_suffix(".txt").read_text(encoding="utf-8")
    assert _core.base2048_encode(payload) == expected


@pytest.mark.parametrize("n", range(601))
@pytest.mark.parametrize("flavor", PAYLOAD_FLAVORS)
def test_encode_matches_reference_every_length(flavor: str, n: int) -> None:
    """Every tail shape at every small length; broken tail math can't hide."""
    payload = PAYLOAD_FLAVORS[flavor](n)
    assert _core.base2048_encode(payload) == base2048_reference.encode(payload)


@given(st.binary())
def test_encode_matches_reference(payload: bytes) -> None:
    assert _core.base2048_encode(payload) == base2048_reference.encode(payload)


@pytest.mark.parametrize("view", [bytes, bytearray, memoryview])
def test_encode_accepts_any_buffer(view: Callable[[bytes], ReadableBuffer]) -> None:
    """The charter: encode() accepts any buffer-protocol object, not just bytes."""
    payload = random.Random(99).randbytes(187)
    assert _core.base2048_encode(view(payload)) == _core.base2048_encode(payload)


def test_encode_matches_reference_megabyte() -> None:
    """The vectors stop at 768 KiB; size-dependent bugs live past that."""
    payload = random.Random(2**20).randbytes(2**20)
    assert _core.base2048_encode(payload) == base2048_reference.encode(payload)


@pytest.mark.parametrize(("payload", "expected"), list(error_cases.NARROW_PINS.items()), ids=repr)
def test_narrow_output_is_a_canonical_str(payload: bytes, expected: str) -> None:
    """The repertoire starts in ASCII; a str in a wider kind than its content would compare and hash unequal."""
    encoded = _core.base2048_encode(payload)
    assert encoded == expected
    assert max(map(ord, encoded)) < 0x100
    assert {encoded} == {expected}  # hashing agrees, not only equality
    assert _core.base2048_decode(expected) == payload


def test_every_single_byte_round_trips_through_the_narrow_path() -> None:
    """Bytes 0 to 6 come back as 1-byte-kind strings, 7 onward as 2-byte; all must equal the oracle."""
    for value in range(256):
        payload = bytes([value])
        encoded = _core.base2048_encode(payload)
        assert encoded == base2048_reference.encode(payload)
        assert (max(map(ord, encoded)) < 0x100) is (value <= 6)
        assert _core.base2048_decode(encoded) == payload


@pytest.mark.parametrize("z", range(8))
def test_short_alphabet_from_first_principles(z: int) -> None:
    """Ten bytes leave exactly 3 bits, the low bits of the last byte, one short character each."""
    assert _core.base2048_encode(bytes(9) + bytes([z]))[-1] == chr(ord("0") + z)


@pytest.mark.parametrize("bad", ["text", 42], ids=["str", "int"])
def test_encode_rejects_non_buffer(bad: str | int) -> None:
    """The exact prose is the platform's; match only the load-bearing phrase."""
    with pytest.raises(TypeError, match="bytes-like"):
        _core.base2048_encode(bad)  # pyright: ignore[reportArgumentType]


@pytest.mark.parametrize("func", [_core.base2048_encode, _core.base2048_decode])
def test_signature_is_pinned(func: Callable[..., object]) -> None:
    """Fails if the text-signature block in the C docstring is mangled or lost."""
    assert str(inspect.signature(func)) == "(data, /)"


def test_decode_conformance(base2048_bin_path: pathlib.Path) -> None:
    payload = base2048_bin_path.read_bytes()
    encoded = base2048_bin_path.with_suffix(".txt").read_text(encoding="utf-8")
    assert _core.base2048_decode(encoded) == payload


@pytest.mark.parametrize("n", range(601))
@pytest.mark.parametrize("flavor", PAYLOAD_FLAVORS)
def test_decode_inverts_reference_encode(flavor: str, n: int) -> None:
    payload = PAYLOAD_FLAVORS[flavor](n)
    assert _core.base2048_decode(base2048_reference.encode(payload)) == payload


@pytest.mark.parametrize("n", range(601))
@pytest.mark.parametrize("flavor", PAYLOAD_FLAVORS)
def test_reference_decode_inverts_encode(flavor: str, n: int) -> None:
    payload = PAYLOAD_FLAVORS[flavor](n)
    assert base2048_reference.decode(_core.base2048_encode(payload)) == payload


@given(st.binary())
def test_round_trip(payload: bytes) -> None:
    """The C-only loop at unbounded lengths; the cross arrows are sweep-covered."""
    assert _core.base2048_decode(_core.base2048_encode(payload)) == payload


@pytest.mark.parametrize("name", sorted(error_cases.BAD_CASES))
def test_decode_rejects_bad_input(name: str, vector_dir: pathlib.Path) -> None:
    bad = (vector_dir / "bad" / f"{name}.txt").read_text(encoding="utf-8")
    with pytest.raises(_core.DecodeError) as exc_info:
        _core.base2048_decode(bad)
    assert exc_info.value.position == error_cases.BAD_CASES[name]


@pytest.mark.parametrize(
    ("string", "position"),
    error_cases.HOSTILE_CASES.values(),
    ids=error_cases.HOSTILE_CASES,
)
def test_decode_rejects_hostile_input(string: str, position: int) -> None:
    """In-table cells the alphabet leaves invalid, both sides of the table's end, surrogates and astral characters."""
    with pytest.raises(_core.DecodeError) as exc_info:
        _core.base2048_decode(string)
    assert exc_info.value.position == position


@pytest.mark.parametrize(
    ("string", "position"),
    error_cases.PADDING_CASES.values(),
    ids=error_cases.PADDING_CASES,
)
def test_decode_rejects_zeroed_padding(string: str, position: int) -> None:
    with pytest.raises(_core.DecodeError) as exc_info:
        _core.base2048_decode(string)
    assert exc_info.value.position == position


@pytest.mark.parametrize(
    ("string", "position"),
    error_cases.SHORT_CASES.values(),
    ids=error_cases.SHORT_CASES,
)
def test_decode_rejects_short_character_before_the_end(string: str, position: int) -> None:
    with pytest.raises(_core.DecodeError) as exc_info:
        _core.base2048_decode(string)
    assert exc_info.value.position == position


@pytest.mark.parametrize(
    ("string", "position"),
    error_cases.CANONICALITY_CASES.values(),
    ids=error_cases.CANONICALITY_CASES,
)
def test_decode_rejects_zero_payload_final_character(string: str, position: int) -> None:
    """The deliberate qntm divergence, enforced identically on both sides."""
    with pytest.raises(_core.DecodeError) as exc_info:
        _core.base2048_decode(string)
    assert exc_info.value.position == position


def test_decode_empty_string_is_empty_payload() -> None:
    assert _core.base2048_decode("") == b""


def _type_id(value: object) -> str:
    return type(value).__name__


@pytest.mark.parametrize("bad", error_cases.NON_STR_INPUTS, ids=_type_id)
def test_decode_rejects_non_str(bad: object) -> None:
    with pytest.raises(TypeError):
        _core.base2048_decode(bad)  # pyright: ignore[reportArgumentType]


def test_decode_matches_reference_megabyte() -> None:
    """The encode twin's mirror: size-dependent bugs, decode direction."""
    payload = random.Random(2**20).randbytes(2**20)
    assert _core.base2048_decode(base2048_reference.encode(payload)) == payload
