"""Fuzz the C decoder against the oracle over hostile input spaces."""

from __future__ import annotations

import random

import pytest
from hypothesis import given
from hypothesis import settings
from hypothesis import strategies as st

from radixly import _core
from tests.reference import base32768 as base32768_reference
from tests.reference import errors as errors_reference


def _assert_parity(string: str) -> bytes | None:
    """C and the oracle must agree exactly; returns the payload on accept."""
    try:
        expected = base32768_reference.decode(string)
    except errors_reference.DecodeError as reference_error:
        expected_position = reference_error.position
    else:
        result = _core.base32768_decode(string)
        assert result == expected
        return result
    with pytest.raises(_core.DecodeError) as exc_info:
        _core.base32768_decode(string)
    assert exc_info.value.position == expected_position
    return None


def _join_chars(code_points: list[int]) -> str:
    return "".join(chr(code_point) for code_point in code_points)


# Shape A: raw code points, because st.text() never generates lone surrogates.
BMP_STRINGS = st.lists(st.integers(min_value=0, max_value=0xFFFF)).map(_join_chars)
FULL_RANGE_STRINGS = st.lists(st.integers(min_value=0, max_value=0x10FFFF)).map(_join_chars)


@given(BMP_STRINGS)
def test_fuzz_bmp_strings(string: str) -> None:
    _assert_parity(string)


@given(FULL_RANGE_STRINGS)
def test_fuzz_full_range_strings(string: str) -> None:
    _assert_parity(string)


# Shape B: mutate valid encodings to reach the deep rejections random strings never hit.
_ALPHABET: str = "".join(base32768_reference.LOOKUP_D)
# one_of: in a single flat pool the 4 hostiles would be ~1-in-8000 draws.
_MUTATION_POOL = st.one_of(
    st.sampled_from(_ALPHABET),
    st.sampled_from("A\x00\ud800\U0001f600"),
)


@st.composite
def _corrupted_encodings(draw: st.DrawFn) -> str:
    encoded = base32768_reference.encode(draw(st.binary()))
    mutation = draw(st.sampled_from(["replace", "insert", "delete", "truncate"]))
    if mutation == "insert":
        position = draw(st.integers(min_value=0, max_value=len(encoded)))
        return encoded[:position] + draw(_MUTATION_POOL) + encoded[position:]
    if not encoded:
        return draw(_MUTATION_POOL)  # nothing to mutate in place; a 1-char probe
    position = draw(st.integers(min_value=0, max_value=len(encoded) - 1))
    if mutation == "replace":
        return encoded[:position] + draw(_MUTATION_POOL) + encoded[position + 1 :]
    if mutation == "delete":
        return encoded[:position] + encoded[position + 1 :]
    return encoded[:position]  # truncate


@settings(max_examples=500)
@given(_corrupted_encodings())
def test_fuzz_corrupted_encodings(string: str) -> None:
    _assert_parity(string)


# Shape C: not Hypothesis — the one exhaustive statement in the suite.


def test_every_single_character_agrees() -> None:
    """Every reverse-table cell; exactly 256 single chars decode (all-ones low 7 bits)."""
    accepted = sum(1 for code_point in range(0x10000) if _assert_parity(chr(code_point)) is not None)
    assert accepted == 256


def test_multi_megabyte_hostile_tail() -> None:
    """Multi-MB hostile tail: correct position deep into big input. Payload is a
    multiple of 15 so no 7-bit final char would fail one index earlier."""
    payload = random.Random(3_000_000).randbytes(3_000_000)
    corrupted = base32768_reference.encode(payload) + "\ud800"
    hostile_index = len(corrupted) - 1
    assert hostile_index == 1_600_000  # 8 * 3e6 / 15: the length math, pinned
    with pytest.raises(_core.DecodeError) as c_info:
        _core.base32768_decode(corrupted)
    with pytest.raises(errors_reference.DecodeError) as reference_info:
        base32768_reference.decode(corrupted)
    assert (c_info.value.position, reference_info.value.position) == (hostile_index, hostile_index)
