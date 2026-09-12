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
"""Fuzz the C decoder against the oracle over hostile input spaces."""

from __future__ import annotations

import random

import pytest
from hypothesis import given
from hypothesis import settings
from hypothesis import strategies as st

from radixly import _core
from tests.reference import base2048 as base2048_reference
from tests.reference import errors as errors_reference


def _assert_parity(string: str) -> bytes | None:
    """C and the oracle must agree exactly; returns the payload on accept."""
    try:
        expected = base2048_reference.decode(string)
    except errors_reference.DecodeError as reference_error:
        expected_position = reference_error.position
    else:
        result = _core.base2048_decode(string)
        assert result == expected
        return result
    with pytest.raises(_core.DecodeError) as exc_info:
        _core.base2048_decode(string)
    assert exc_info.value.position == expected_position
    return None


def _join_chars(code_points: list[int]) -> str:
    return "".join(chr(code_point) for code_point in code_points)


LIGHT_STRINGS = st.lists(st.integers(min_value=0, max_value=0x10FF)).map(_join_chars)
FULL_RANGE_STRINGS = st.lists(st.integers(min_value=0, max_value=0x10FFFF)).map(_join_chars)


@given(LIGHT_STRINGS)
def test_fuzz_light_strings(string: str) -> None:
    """Code points up to U+10FF: dense hits inside the table and just past its U+1055 end."""
    _assert_parity(string)


@given(FULL_RANGE_STRINGS)
def test_fuzz_full_range_strings(string: str) -> None:
    _assert_parity(string)


_ALPHABET: str = "".join(base2048_reference.LOOKUP_D)
_MUTATION_POOL = st.one_of(
    st.sampled_from(_ALPHABET),
    st.sampled_from("!\x00ᄀ\ud800\U0001f600"),
)


@st.composite
def _corrupted_encodings(draw: st.DrawFn) -> str:
    encoded = base2048_reference.encode(draw(st.binary()))
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


def test_every_single_character_agrees() -> None:
    """Every reverse-table cell; exactly 256 single chars decode (all-ones low 3 bits of an 11-bit one)."""
    accepted = sum(1 for code_point in range(0x10000) if _assert_parity(chr(code_point)) is not None)
    assert accepted == 256


def test_multi_megabyte_hostile_tail() -> None:
    """Correct position deep into a multi-MB input; payload is a multiple of 11 so no 3-bit char fails earlier."""
    payload = random.Random(2_999_997).randbytes(2_999_997)
    corrupted = base2048_reference.encode(payload) + "\ud800"
    hostile_index = len(corrupted) - 1
    assert hostile_index == 2_181_816  # 8 * 2999997 / 11: the length math, pinned
    with pytest.raises(_core.DecodeError) as c_info:
        _core.base2048_decode(corrupted)
    with pytest.raises(errors_reference.DecodeError) as reference_info:
        base2048_reference.decode(corrupted)
    assert (c_info.value.position, reference_info.value.position) == (hostile_index, hostile_index)
