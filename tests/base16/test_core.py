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
"""Differential and rejection tests: the C base16 codec against its oracle and the RFC vectors."""

from __future__ import annotations

import inspect
import random
import typing

import pytest
from hypothesis import given
from hypothesis import settings
from hypothesis import strategies as st

from radixly import _core
from tests.base16 import error_cases
from tests.payloads import PAYLOAD_FLAVORS
from tests.reference import base16 as base16_reference
from tests.reference import errors as errors_reference

if typing.TYPE_CHECKING:
    from collections.abc import Callable

    from _typeshed import ReadableBuffer


def _assert_parity(string: str) -> bytes | None:
    """C and the oracle must agree exactly; returns the payload on accept."""
    try:
        expected = base16_reference.decode(string)
    except errors_reference.DecodeError as reference_error:
        expected_position = reference_error.position
    else:
        result = _core.base16_decode(string)
        assert result == expected
        return result
    with pytest.raises(_core.DecodeError) as exc_info:
        _core.base16_decode(string)
    assert exc_info.value.position == expected_position
    return None


def test_case_tables_are_nonempty() -> None:
    """An emptied table would collect zero cases and stay green."""
    assert all(len(table) > 0 for table in (PAYLOAD_FLAVORS, error_cases.RFC_VECTORS, error_cases.INVALID_CASES))


@pytest.mark.parametrize(("payload", "expected"), list(error_cases.RFC_VECTORS.items()), ids=repr)
def test_rfc_vectors(payload: bytes, expected: str) -> None:
    """RFC 4648 section 10, both directions."""
    assert _core.base16_encode(payload) == expected
    assert _core.base16_decode(expected) == payload


@pytest.mark.parametrize("n", range(601))
@pytest.mark.parametrize("flavor", PAYLOAD_FLAVORS)
def test_encode_matches_reference_every_length(flavor: str, n: int) -> None:
    payload = PAYLOAD_FLAVORS[flavor](n)
    assert _core.base16_encode(payload) == base16_reference.encode(payload)


@pytest.mark.parametrize("n", range(601))
@pytest.mark.parametrize("flavor", PAYLOAD_FLAVORS)
def test_decode_inverts_reference_encode(flavor: str, n: int) -> None:
    payload = PAYLOAD_FLAVORS[flavor](n)
    assert _core.base16_decode(base16_reference.encode(payload)) == payload


@given(st.binary())
def test_round_trip(payload: bytes) -> None:
    assert _core.base16_decode(_core.base16_encode(payload)) == payload


@given(st.binary())
def test_encode_is_uppercase_and_ascii(payload: bytes) -> None:
    encoded = _core.base16_encode(payload)
    assert encoded == encoded.upper()
    assert encoded.isascii()


@pytest.mark.parametrize("view", [bytes, bytearray, memoryview])
def test_encode_accepts_any_buffer(view: Callable[[bytes], ReadableBuffer]) -> None:
    payload = random.Random(99).randbytes(187)
    assert _core.base16_encode(view(payload)) == _core.base16_encode(payload)


def test_encode_rejects_non_contiguous_buffer() -> None:
    """A strided view is refused, as every codec here does; the oracle takes bytes only."""
    with pytest.raises(BufferError, match="contiguous"):
        _core.base16_encode(memoryview(b"abcdef")[::2])


@pytest.mark.parametrize("bad", ["text", 42], ids=["str", "int"])
def test_encode_rejects_non_buffer(bad: str | int) -> None:
    with pytest.raises(TypeError, match="bytes-like"):
        _core.base16_encode(bad)  # pyright: ignore[reportArgumentType]


@pytest.mark.parametrize("func", [_core.base16_encode, _core.base16_decode])
def test_signature_is_pinned(func: Callable[..., object]) -> None:
    assert str(inspect.signature(func)) == "(data, /)"


@pytest.mark.parametrize(("string", "position"), error_cases.INVALID_CASES.values(), ids=error_cases.INVALID_CASES)
def test_decode_rejects_invalid_input(string: str, position: int) -> None:
    with pytest.raises(_core.DecodeError) as exc_info:
        _core.base16_decode(string)
    assert exc_info.value.position == position


def test_decode_empty_string_is_empty_payload() -> None:
    assert _core.base16_decode("") == b""


@pytest.mark.parametrize(
    ("string", "position"),
    [("6869\u0100", 4), ("6869\U0001f600", 4), ("\u010068", 0), ("68\u0100" + "69" * 4, 2), ("68\U0001f600" * 3, 2)],
)
def test_decode_reads_every_str_kind(string: str, position: int) -> None:
    """A 2-byte or 4-byte str takes the wide path and reports its first invalid character at its index."""
    with pytest.raises(_core.DecodeError) as exc_info:
        _core.base16_decode(string)
    assert exc_info.value.position == position
    with pytest.raises(errors_reference.DecodeError) as reference_info:
        base16_reference.decode(string)
    assert reference_info.value.position == position


def test_megabyte_hostile_tail() -> None:
    """Four megabytes of valid digits, then one bad character: the position is the tail's, not the length's."""
    valid = _core.base16_encode(random.Random(4).randbytes(2**21))
    for bad in ("g", "=", "\xff", "\u0100", "\U0001f600"):
        with pytest.raises(_core.DecodeError) as exc_info:
            _core.base16_decode(valid + bad + "00")
        assert exc_info.value.position == len(valid)


def _type_id(value: object) -> str:
    return type(value).__name__


@pytest.mark.parametrize("bad", error_cases.NON_STR_INPUTS, ids=_type_id)
def test_decode_rejects_non_str(bad: object) -> None:
    with pytest.raises(TypeError):
        _core.base16_decode(bad)  # pyright: ignore[reportArgumentType]


def test_megabyte_differential() -> None:
    payload = random.Random(2**20).randbytes(2**20)
    encoded = _core.base16_encode(payload)
    assert encoded == base16_reference.encode(payload)
    assert _core.base16_decode(encoded) == payload


_MUTATION_POOL = st.sampled_from("0123456789ABCDEFabcdefg =!\x00\ud800\U0001f600")


@st.composite
def _corrupted_encodings(draw: st.DrawFn) -> str:
    encoded = base16_reference.encode(draw(st.binary()))
    mutation = draw(st.sampled_from(["replace", "insert", "delete", "truncate"]))
    if mutation == "insert":
        position = draw(st.integers(min_value=0, max_value=len(encoded)))
        return encoded[:position] + draw(_MUTATION_POOL) + encoded[position:]
    if not encoded:
        return draw(_MUTATION_POOL)
    position = draw(st.integers(min_value=0, max_value=len(encoded) - 1))
    if mutation == "replace":
        return encoded[:position] + draw(_MUTATION_POOL) + encoded[position + 1 :]
    if mutation == "delete":
        return encoded[:position] + encoded[position + 1 :]
    return encoded[:position]


@settings(max_examples=500)
@given(_corrupted_encodings())
def test_fuzz_corrupted_encodings(string: str) -> None:
    _assert_parity(string)


@given(st.lists(st.integers(min_value=0, max_value=0x10FFFF)).map(lambda cps: "".join(map(chr, cps))))
def test_fuzz_full_range_strings(string: str) -> None:
    _assert_parity(string)


def test_every_single_character_agrees() -> None:
    """Every one-character string: none decodes (a byte needs two digits), positions agree."""
    accepted = sum(1 for code_point in range(0x10000) if _assert_parity(chr(code_point)) is not None)
    assert accepted == 0
