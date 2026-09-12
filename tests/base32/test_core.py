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
"""Differential and rejection tests: the C base32 presets against their oracles and the RFC vectors."""

from __future__ import annotations

import inspect
import random
import typing

import pytest
from hypothesis import given
from hypothesis import settings
from hypothesis import strategies as st

from radixly import _core
from tests.base32 import error_cases
from tests.payloads import PAYLOAD_FLAVORS
from tests.reference import errors as errors_reference

if typing.TYPE_CHECKING:
    from collections.abc import Callable

    from _typeshed import ReadableBuffer

C_ENCODE: dict[str, Callable[[ReadableBuffer], str]] = {
    "base32": _core.base32_encode,
    "base32hex": _core.base32hex_encode,
}
C_DECODE: dict[str, Callable[[str], bytes]] = {
    "base32": _core.base32_decode,
    "base32hex": _core.base32hex_decode,
}


def _assert_parity(preset: str, string: str) -> bytes | None:
    """C and the oracle must agree exactly; returns the payload on accept."""
    try:
        expected = error_cases.PRESETS[preset].decode(string)
    except errors_reference.DecodeError as reference_error:
        expected_position = reference_error.position
    else:
        result = C_DECODE[preset](string)
        assert result == expected
        return result
    with pytest.raises(_core.DecodeError) as exc_info:
        C_DECODE[preset](string)
    assert exc_info.value.position == expected_position
    return None


def test_case_tables_are_nonempty() -> None:
    """An emptied table would collect zero cases and stay green."""
    assert len(error_cases.INVALID_KINDS) > 0
    assert all(len(vectors) > 0 for vectors in error_cases.RFC_VECTORS.values())
    assert len(PAYLOAD_FLAVORS) > 0


@pytest.mark.parametrize("preset", error_cases.PRESETS)
def test_rfc_vectors(preset: str) -> None:
    """RFC 4648 section 10, both directions."""
    for payload, expected in error_cases.RFC_VECTORS[preset].items():
        assert C_ENCODE[preset](payload) == expected
        assert C_DECODE[preset](expected) == payload


@pytest.mark.parametrize("n", range(601))
@pytest.mark.parametrize("flavor", PAYLOAD_FLAVORS)
@pytest.mark.parametrize("preset", error_cases.PRESETS)
def test_encode_matches_reference_every_length(preset: str, flavor: str, n: int) -> None:
    payload = PAYLOAD_FLAVORS[flavor](n)
    assert C_ENCODE[preset](payload) == error_cases.PRESETS[preset].encode(payload)


@pytest.mark.parametrize("n", range(601))
@pytest.mark.parametrize("flavor", PAYLOAD_FLAVORS)
@pytest.mark.parametrize("preset", error_cases.PRESETS)
def test_decode_inverts_reference_encode(preset: str, flavor: str, n: int) -> None:
    payload = PAYLOAD_FLAVORS[flavor](n)
    assert C_DECODE[preset](error_cases.PRESETS[preset].encode(payload)) == payload


@pytest.mark.parametrize("preset", error_cases.PRESETS)
@given(payload=st.binary())
def test_round_trip(preset: str, payload: bytes) -> None:
    assert C_DECODE[preset](C_ENCODE[preset](payload)) == payload


@pytest.mark.parametrize("preset", error_cases.PRESETS)
@given(payload=st.binary())
def test_output_is_padded_uppercase_ascii(preset: str, payload: bytes) -> None:
    encoded = C_ENCODE[preset](payload)
    assert len(encoded) % 8 == 0
    assert encoded == encoded.upper()
    assert encoded.isascii()


@pytest.mark.parametrize("view", [bytes, bytearray, memoryview])
@pytest.mark.parametrize("preset", error_cases.PRESETS)
def test_encode_accepts_any_buffer(preset: str, view: Callable[[bytes], ReadableBuffer]) -> None:
    payload = random.Random(99).randbytes(187)
    assert C_ENCODE[preset](view(payload)) == C_ENCODE[preset](payload)


@pytest.mark.parametrize("preset", error_cases.PRESETS)
def test_encode_rejects_non_contiguous_buffer(preset: str) -> None:
    with pytest.raises(BufferError, match="contiguous"):
        C_ENCODE[preset](memoryview(b"abcdef")[::2])


@pytest.mark.parametrize("bad", ["text", 42], ids=["str", "int"])
@pytest.mark.parametrize("preset", error_cases.PRESETS)
def test_encode_rejects_non_buffer(preset: str, bad: str | int) -> None:
    with pytest.raises(TypeError, match="bytes-like"):
        C_ENCODE[preset](bad)  # pyright: ignore[reportArgumentType]


@pytest.mark.parametrize("func", [*C_ENCODE.values(), *C_DECODE.values()])
def test_signature_is_pinned(func: Callable[..., object]) -> None:
    assert str(inspect.signature(func)) == "(data, /)"


@pytest.mark.parametrize("kind", error_cases.INVALID_KINDS)
@pytest.mark.parametrize("preset", error_cases.PRESETS)
def test_decode_rejects_invalid_input(preset: str, kind: str) -> None:
    string, position = error_cases.INVALID_CASES[preset][kind]
    with pytest.raises(_core.DecodeError) as exc_info:
        C_DECODE[preset](string)
    assert exc_info.value.position == position


@pytest.mark.parametrize("preset", error_cases.PRESETS)
def test_decode_empty_string_is_empty_payload(preset: str) -> None:
    assert C_DECODE[preset]("") == b""


def _type_id(value: object) -> str:
    return type(value).__name__


@pytest.mark.parametrize("bad", error_cases.NON_STR_INPUTS, ids=_type_id)
@pytest.mark.parametrize("preset", error_cases.PRESETS)
def test_decode_rejects_non_str(preset: str, bad: object) -> None:
    with pytest.raises(TypeError):
        C_DECODE[preset](bad)  # pyright: ignore[reportArgumentType]


@pytest.mark.parametrize("preset", error_cases.PRESETS)
def test_megabyte_differential(preset: str) -> None:
    payload = random.Random(2**20).randbytes(2**20)
    encoded = C_ENCODE[preset](payload)
    assert encoded == error_cases.PRESETS[preset].encode(payload)
    assert C_DECODE[preset](encoded) == payload


def _mutation_pool(preset: str) -> st.SearchStrategy[str]:
    alphabet = error_cases.PRESETS[preset].ALPHABET
    return st.one_of(st.sampled_from(alphabet + "="), st.sampled_from(alphabet.lower() + "! \x00\ud800\U0001f600"))


@st.composite
def _corrupted_encodings(draw: st.DrawFn, preset: str) -> str:
    encoded = error_cases.PRESETS[preset].encode(draw(st.binary()))
    pool = _mutation_pool(preset)
    mutation = draw(st.sampled_from(["replace", "insert", "delete", "truncate"]))
    if mutation == "insert":
        position = draw(st.integers(min_value=0, max_value=len(encoded)))
        return encoded[:position] + draw(pool) + encoded[position:]
    if not encoded:
        return draw(pool)
    position = draw(st.integers(min_value=0, max_value=len(encoded) - 1))
    if mutation == "replace":
        return encoded[:position] + draw(pool) + encoded[position + 1 :]
    if mutation == "delete":
        return encoded[:position] + encoded[position + 1 :]
    return encoded[:position]


@pytest.mark.parametrize("preset", error_cases.PRESETS)
@settings(max_examples=500)
@given(data=st.data())
def test_fuzz_corrupted_encodings(preset: str, data: st.DataObject) -> None:
    _assert_parity(preset, data.draw(_corrupted_encodings(preset)))


@pytest.mark.parametrize("preset", error_cases.PRESETS)
@given(data=st.data())
def test_fuzz_full_range_strings(preset: str, data: st.DataObject) -> None:
    code_points = data.draw(st.lists(st.integers(min_value=0, max_value=0x10FFFF)))
    _assert_parity(preset, "".join(map(chr, code_points)))


@pytest.mark.parametrize("preset", error_cases.PRESETS)
def test_every_single_character_agrees(preset: str) -> None:
    """Every one-character string: none decodes (a group needs eight), positions agree."""
    accepted = sum(1 for code_point in range(0x10000) if _assert_parity(preset, chr(code_point)) is not None)
    assert accepted == 0


@pytest.mark.parametrize("preset", error_cases.PRESETS)
def test_every_padded_group_shape(preset: str) -> None:
    """All 256 first-byte values through every tail length, so every pad-bit mask meets a real payload."""
    module = error_cases.PRESETS[preset]
    for tail in range(1, 5):
        for value in range(256):
            payload = bytes([value] * tail)
            encoded = C_ENCODE[preset](payload)
            assert encoded == module.encode(payload)
            assert C_DECODE[preset](encoded) == payload
