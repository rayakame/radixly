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

import base64
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


STDLIB_DECODE: dict[str, Callable[[str], bytes]] = {
    "base32": base64.b32decode,
    "base32hex": base64.b32hexdecode,
}


def _assert_parity(preset: str, string: str) -> bytes | None:
    """C and the reference must agree exactly, and what they accept the standard library reads the same way."""
    try:
        expected = error_cases.PRESETS[preset].decode(string)
    except errors_reference.DecodeError as reference_error:
        expected_position = reference_error.position
    else:
        result = C_DECODE[preset](string)
        assert result == expected
        assert STDLIB_DECODE[preset](string) == expected
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
def test_encode_matches_reference(preset: str, payload: bytes) -> None:
    assert C_ENCODE[preset](payload) == error_cases.PRESETS[preset].encode(payload)


@pytest.mark.parametrize(("preset", "foreign"), [("base32", "0189"), ("base32hex", "WXYZ")])
def test_the_other_alphabet_is_refused(preset: str, foreign: str) -> None:
    """The two presets share one C core; a character from the other alphabet is a reverse-table mix-up."""
    for char in foreign:
        for string in (char * 8, "A" * 7 + char, char + "A" * 7):
            _assert_parity(preset, string)
            with pytest.raises(_core.DecodeError) as exc_info:
                C_DECODE[preset](string)
            assert exc_info.value.position == string.index(char)


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
def test_every_byte_in_every_slot_of_every_tail(preset: str) -> None:
    """Every byte value in every slot of every tail length, C against the reference both ways."""
    module = error_cases.PRESETS[preset]
    for tail in range(1, 5):
        for slot in range(tail):
            for value in range(256):
                payload = bytes(value if i == slot else 0x5A for i in range(tail))
                encoded = C_ENCODE[preset](payload)
                assert encoded == module.encode(payload)
                assert _assert_parity(preset, encoded) == payload


@pytest.mark.parametrize("preset", error_cases.PRESETS)
def test_every_last_data_character_of_every_padded_shape(preset: str) -> None:
    """Each alphabet character closing each padded shape: only the ones with zero pad bits pass, positions agree."""
    alphabet = error_cases.PRESETS[preset].ALPHABET
    accepted_by_shape = {2: 8, 4: 2, 5: 16, 7: 4}
    for data_chars, expected in accepted_by_shape.items():
        strings = [alphabet[0] * (data_chars - 1) + last + "=" * (8 - data_chars) for last in alphabet]
        accepted = sum(1 for string in strings if _assert_parity(preset, string) is not None)
        assert accepted == expected


_HOSTILE_CHARS = "a=!\x00\x7f\xff\u0100\ud800\U0001f600"


@pytest.mark.parametrize("preset", error_cases.PRESETS)
def test_every_position_meets_every_hostile_character(preset: str) -> None:
    """A hostile character replacing or joining each position of a padded encoding: positions agree everywhere."""
    encoded = C_ENCODE[preset](b"radixly base32")
    assert encoded.endswith("=")
    for position in range(len(encoded) + 1):
        for bad in _HOSTILE_CHARS:
            _assert_parity(preset, encoded[:position] + bad + encoded[position:])
            _assert_parity(preset, encoded[:position] + bad + encoded[position + 1 :])
            _assert_parity(preset, encoded[:position] + bad)


@pytest.mark.parametrize("preset", error_cases.PRESETS)
def test_megabyte_hostile_tail(preset: str) -> None:
    """Megabytes of valid groups, then one bad character: the position is the tail's, not the length's."""
    valid = C_ENCODE[preset](random.Random(5).randbytes(5 * 2**19))
    assert len(valid) % 8 == 0
    for bad in ("a", "=", "\xff", "\u0100", "\U0001f600"):
        for prefix in ("", "AA"):
            with pytest.raises(_core.DecodeError) as exc_info:
                C_DECODE[preset](valid + prefix + bad + "AAAAAAAA")
            offender = 1 if bad == "=" else 0  # padding may stand there; the data character after it may not
            assert exc_info.value.position == len(valid) + len(prefix) + offender
